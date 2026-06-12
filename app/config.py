import os
import shutil
import sys
from pathlib import Path


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


BASE_DIR = get_base_dir()

# Search exe directory first so local ffmpeg takes priority over system PATH.
_exe_ffmpeg = BASE_DIR / "ffmpeg.exe"
_exe_ffprobe = BASE_DIR / "ffprobe.exe"

FFMPEG_PATH = str(_exe_ffmpeg) if _exe_ffmpeg.exists() else shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = str(_exe_ffprobe) if _exe_ffprobe.exists() else shutil.which("ffprobe") or "ffprobe"

IGNORE_DIRS = {'output', 'fonts', 'python', '__pycache__', '.git', '.venv', 'app'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.rmvb'}
SUBTITLE_EXTENSIONS = {'.ass', '.srt'}
PREFERRED_LANG = 'SC'
