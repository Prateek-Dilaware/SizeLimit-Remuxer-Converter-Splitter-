# MKV to MP4 Converter & Splitter

A fast, automated Python utility powered by FFmpeg for batch-converting video files into standard `.mp4` format. It features smart stream remuxing (zero quality loss), high-quality transcoding fallback, and automatic video slicing for files exceeding 1.8 GB.

---

## Features

- **Multi-Format Batch Support**: Converts `.mkv`, `.avi`, `.mov`, `.flv`, `.webm`, `.wmv`, `.m4v`, `.ts`, and `.3gp` files into `.mp4`.
- **Lossless Remuxing First**: Attempts fast stream copying (`-c copy`) first, finishing in seconds with 100% original quality and minimal CPU usage.
- **High-Quality Transcoding Fallback**: If streams are incompatible with direct copy, seamlessly falls back to H.264 (`libx264`, CRF 18 visually lossless) and AAC audio (192 kbps).
- **Automatic File Splitting (> 1.8 GB)**:
  - Any video larger than 1.8 GB (including existing oversized `.mp4` files) is automatically calculated and split into sequential chunks (`<filename>_part_1.mp4`, `<filename>_part_2.mp4`, etc.).
  - Targets ~1.72 GB chunks with a safety margin to guarantee each part remains strictly under 1.8 GB (ideal for platforms with file upload restrictions).
- **Auto-Discovery of FFmpeg**: Automatically locates `ffmpeg` and `ffprobe` in your system `PATH`, with built-in Windows fallback detection for WinGet installations.

---

## Directory Behavior: Are Folders Created Automatically?

| Directory | Auto-Created? | Behavior |
| :--- | :---: | :--- |
| **`Input_vid/`** | **Yes** | If `Input_vid` does not exist when the script runs, the script **automatically creates it**, informs you to place your source videos inside, and exits cleanly. You can also create this folder manually beforehand. |
| **`Output_vid/`** | **Yes** | If `Output_vid` does not exist, the script **automatically creates it** on startup and begins saving converted videos directly into it without interruption. |

> **Note on Version Control:** The `Output_vid/` folder is excluded in `.gitignore` to keep large converted video outputs out of your Git repository.

---

## Prerequisites

1. **Python 3.10+** (standard library only; no external `pip` dependencies are required to run `convert_videos.py`).
2. **FFmpeg & FFprobe**:
   - **Windows (WinGet)**:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **Windows (Manual)**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin` directory to your system `PATH`.
   - **macOS**:
     ```bash
     brew install ffmpeg
     ```
   - **Linux (Ubuntu/Debian)**:
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```

---

## Quick Start

### 1. Clone or Open the Repository
```bash
git clone <repo-url>
cd mkv_to_MP4
```

### 2. Place Your Videos in `Input_vid`
- You can manually create the `Input_vid` folder, or simply run the script once to let it create the directory for you:
  ```bash
  python convert_videos.py
  ```
- Copy any `.mkv`, `.avi`, `.mov`, etc., or oversized `.mp4` files into `Input_vid/`.

### 3. Run the Conversion Script
```bash
python convert_videos.py
```
*(Or with `uv` if using uv virtual environments)*:
```bash
uv run python convert_videos.py
```

### 4. Collect Your Output
All converted files and split parts are written directly to `Output_vid/`.

---

## Project Structure

```text
mkv_to_MP4/
├── Input_vid/             # Source videos placed here (auto-created if missing)
├── Output_vid/            # Converted MP4s and split parts (auto-created, ignored by git)
├── convert_videos.py      # Core conversion and splitting script
├── pyproject.toml         # Project metadata and dependencies (uv / pip)
├── .gitignore             # Git ignore rules (includes Output_vid/ and venv)
└── README.md              # Project documentation
```

---

## How It Works

1. **FFmpeg Validation**: Verifies `ffmpeg` and `ffprobe` availability.
2. **Directory Check**: Ensures `Input_vid` and `Output_vid` exist (creating them automatically if they are missing).
3. **Queue Filtering**:
   - Files with supported non-MP4 extensions (`.mkv`, `.avi`, etc.) are queued for conversion.
   - `.mp4` files are skipped if they are $\le 1.8\text{ GB}$.
   - `.mp4` files larger than $1.8\text{ GB}$ are automatically queued for chunk splitting.
4. **Processing & Conversion**:
   - If file size $\le 1.8\text{ GB}$: remuxes or transcodes directly to a single `.mp4` file.
   - If file size $> 1.8\text{ GB}$: probes video duration, calculates bitrate, and sequentially slices the video into parts strictly under 1.8 GB.
5. **Summary Report**: Prints total successful and failed conversions along with the output destination.
