import os
import subprocess
import sys
import glob

# Define input and output directory paths
# We use relative paths based on the script location to make it portable.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "Input_vid")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "Output_vid")

# List of common video formats to search for (excluding .mp4)
CONVERTIBLE_EXTENSIONS = {'.mkv', '.avi', '.mov', '.flv', '.webm', '.wmv', '.m4v', '.ts', '.3gp'}

# Global variable for the ffmpeg executable command/path
FFMPEG_CMD = None

def get_ffmpeg_cmd():
    """
    Finds and returns the command/path to execute ffmpeg.
    1. First checks if 'ffmpeg' is directly available in the system PATH.
    2. If not, searches the user's local WinGet packages folder for ffmpeg.exe.
    """
    # 1. Check system PATH
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return "ffmpeg"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 2. Check WinGet Packages folder (Windows fallback if environment variables are not reloaded yet)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        winget_pattern = os.path.join(
            local_app_data, 
            "Microsoft", "WinGet", "Packages", 
            "Gyan.FFmpeg_*", "**", "ffmpeg.exe"
        )
        # Use recursive glob to find ffmpeg.exe
        matches = glob.glob(winget_pattern, recursive=True)
        if matches:
            resolved_path = os.path.normpath(matches[0])
            print(f"ℹ️ Found FFmpeg installed via WinGet at:\n   '{resolved_path}'")
            return resolved_path

    return None

def get_video_duration(input_path):
    """Gets the duration of the video in seconds using ffprobe."""
    if FFMPEG_CMD == "ffmpeg":
        ffprobe_cmd = "ffprobe"
    else:
        ffprobe_cmd = FFMPEG_CMD.replace("ffmpeg.exe", "ffprobe.exe")
        
    cmd = [
        ffprobe_cmd,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"⚠️ Warning: Could not retrieve video duration: {e}")
        return None

def convert_video_segment(input_path, output_path, start_time=None, duration=None):
    """
    Converts or slices a segment of a video file to .mp4.
    Attempts lossless stream copying first, falling back to transcoding if necessary.
    """
    # 1. Attempt Lossless Remuxing (Copying streams without re-encoding)
    remux_cmd = [FFMPEG_CMD, "-y"]
    
    if start_time is not None:
        remux_cmd.extend(["-ss", f"{start_time:.3f}"])
        
    remux_cmd.extend(["-i", input_path])
    
    if duration is not None:
        remux_cmd.extend(["-t", f"{duration:.3f}"])
        
    remux_cmd.extend(["-c:v", "copy", "-c:a", "copy", output_path])
    
    try:
        result = subprocess.run(remux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"      ⚠️ Lossless stream copy not compatible. Retrying with high-quality transcoding fallback...")
    except Exception as e:
        print(f"      ⚠️ Unexpected error during remuxing: {e}. Retrying with transcoding fallback...")

    # 2. Fallback: High-Quality Transcoding (Re-encoding)
    # Using libx264 with CRF 18 (visually lossless) and AAC audio.
    transcode_cmd = [FFMPEG_CMD, "-y"]
    
    if start_time is not None:
        transcode_cmd.extend(["-ss", f"{start_time:.3f}"])
        
    transcode_cmd.extend(["-i", input_path])
    
    if duration is not None:
        transcode_cmd.extend(["-t", f"{duration:.3f}"])
        
    transcode_cmd.extend([
        "-c:v", "libx264",   # Encode to H.264 video
        "-crf", "18",         # Constant Rate Factor (18 is visually lossless)
        "-preset", "medium",  # Balanced encoding speed vs file size
        "-c:a", "aac",        # Encode to AAC audio (high compatibility)
        "-b:a", "192k",       # 192 kbps audio bitrate for excellent quality
        output_path
    ])
    
    try:
        result = subprocess.run(transcode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"      ❌ Error: Conversion failed. ffmpeg error:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"      ❌ Exception occurred during transcoding: {e}")
        return False

def process_video_file(input_path, base_name):
    """
    Checks video size. If it is <= 1.8 GB, converts/remuxes directly.
    If > 1.8 GB, calculates duration and splits it into chunks of less than 1.8 GB.
    """
    file_size = os.path.getsize(input_path)
    max_size_limit = 1.8 * 1024 * 1024 * 1024 # 1.8 GB in bytes
    
    if file_size <= max_size_limit:
        # Standard conversion (no splitting needed)
        output_name = base_name + ".mp4"
        output_path = os.path.join(OUTPUT_DIR, output_name)
        print(f"🔄 Processing '{os.path.basename(input_path)}' ({(file_size / (1024**3)):.2f} GB)...")
        return convert_video_segment(input_path, output_path, start_time=None, duration=None)
    
    # Needs Splitting!
    print(f"✂️ File is {(file_size / (1024**3)):.2f} GB (exceeds 1.8 GB limit). Preparing to split into parts...")
    duration = get_video_duration(input_path)
    
    if not duration:
        print(f"❌ Error: Cannot split '{os.path.basename(input_path)}' because duration couldn't be resolved.")
        return False
        
    # Calculate bytes per second average bitrate
    bytes_per_sec = file_size / duration
    
    # Target size is 1.72 GB (safety margin to guarantee each part remains strictly under 1.8 GB)
    target_size_limit = 1.72 * 1024 * 1024 * 1024
    part_duration = target_size_limit / bytes_per_sec
    
    print(f"   ⏱️ Video duration: {duration:.2f}s | Average bitrate: {(bytes_per_sec * 8 / 1_000_000):.2f} Mbps")
    print(f"   📦 Splitting into intervals of approx {part_duration:.2f} seconds...")
    
    start_time = 0.0
    part_idx = 1
    all_parts_success = True
    
    while start_time < duration:
        this_part_duration = min(part_duration, duration - start_time)
        if this_part_duration < 1.0: # Skip tiny leftover segments less than 1 second
            break
            
        part_output_name = f"{base_name}_part_{part_idx}.mp4"
        part_output_path = os.path.join(OUTPUT_DIR, part_output_name)
        
        print(f"   -> Slicing [Part {part_idx}] from {start_time:.2f}s to {(start_time + this_part_duration):.2f}s...")
        
        success = convert_video_segment(
            input_path, 
            part_output_path, 
            start_time=start_time, 
            duration=this_part_duration
        )
        
        if not success:
            all_parts_success = False
            print(f"      ❌ Failed to process Part {part_idx}!")
        else:
            # Check the actual resulting size of the part
            part_size = os.path.getsize(part_output_path)
            print(f"      ✅ Part {part_idx} created successfully ({(part_size / (1024**3)):.2f} GB)")
            if part_size > max_size_limit:
                print(f"      ⚠️ Warning: Part {part_idx} ({(part_size / (1024**3)):.2f} GB) slightly exceeded 1.8 GB limit!")
                
        start_time += this_part_duration
        part_idx += 1
        
    return all_parts_success

def main():
    print("==========================================")
    print("      MKV to MP4 Video Converter Tool     ")
    print("==========================================\n")

    # 1. Verify ffmpeg is installed and find its path
    global FFMPEG_CMD
    FFMPEG_CMD = get_ffmpeg_cmd()
    if not FFMPEG_CMD:
        print("❌ Error: 'ffmpeg' was not found on your system PATH or local packages.")
        print("\nTo use this script, you must install FFmpeg:")
        print("1. Download FFmpeg from https://ffmpeg.org/download.html")
        print("2. Extract the files and add the 'bin' folder to your System Environment variables (PATH).")
        print("3. Restart your terminal/IDE and run this script again.\n")
        sys.exit(1)

    # 2. Check if Input directory exists
    if not os.path.exists(INPUT_DIR):
        print(f"Creating input directory: '{INPUT_DIR}'...")
        os.makedirs(INPUT_DIR)
        print("Please place your video files inside the 'Input_vid' directory and run this script again.")
        sys.exit(0)

    # 3. Create Output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        print(f"Creating output directory: '{OUTPUT_DIR}'...")
        os.makedirs(OUTPUT_DIR)

    # 4. Scan Input Directory
    all_files = os.listdir(INPUT_DIR)
    videos_to_convert = []
    skipped_mp4 = 0
    max_size_limit = 1.8 * 1024 * 1024 * 1024 # 1.8 GB

    for file_name in all_files:
        file_path = os.path.join(INPUT_DIR, file_name)
        if os.path.isdir(file_path):
            continue
            
        _, ext = os.path.splitext(file_name)
        ext = ext.lower()
        
        if ext == '.mp4':
            file_size = os.path.getsize(file_path)
            if file_size > max_size_limit:
                videos_to_convert.append(file_name)
            else:
                skipped_mp4 += 1
        elif ext in CONVERTIBLE_EXTENSIONS:
            videos_to_convert.append(file_name)

    # 5. Report scan results
    print(f"📂 Scanning input directory: '{INPUT_DIR}'")
    print(f"   - Found {len(videos_to_convert)} video(s) that need conversion.")
    if skipped_mp4 > 0:
        print(f"   - Skipped {skipped_mp4} video(s) that are already in .mp4 format.")
    print("------------------------------------------")

    if not videos_to_convert:
        print("ℹ️ No convertible videos found in the 'Input_vid' folder.")
        print("Supported formats: .mkv, .avi, .mov, .flv, .webm, .wmv, .m4v, .ts, .3gp")
        sys.exit(0)

    # 6. Process conversions
    success_count = 0
    fail_count = 0

    for index, file_name in enumerate(videos_to_convert, 1):
        input_path = os.path.join(INPUT_DIR, file_name)
        
        # Get base name without extension
        base_name, _ = os.path.splitext(file_name)
        
        print(f"\n[Video {index}/{len(videos_to_convert)}] Preparing '{file_name}'...")
        
        if process_video_file(input_path, base_name):
            success_count += 1
        else:
            fail_count += 1

    # 7. Summary
    print("\n==========================================")
    print("             Conversion Summary            ")
    print("==========================================")
    print(f"✅ Successfully converted: {success_count} file(s)")
    if fail_count > 0:
        print(f"❌ Failed to convert:     {fail_count} file(s)")
    print(f"📂 Saved to directory:    {OUTPUT_DIR}")
    print("==========================================\n")

if __name__ == "__main__":
    main()
