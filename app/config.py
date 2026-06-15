import os
import sys
from pathlib import Path

from app.core.platform import resolve_ffmpeg, resolve_ffprobe


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


BASE_DIR = get_base_dir()

FFMPEG_PATH = resolve_ffmpeg(BASE_DIR)
FFPROBE_PATH = resolve_ffprobe(BASE_DIR)

IGNORE_DIRS = {
    'output', 'fonts', 'python', 'venv',
    '__pycache__', '.git', '.venv', 'app',
    '.mypy_cache', '.pytest_cache', '.ruff_cache',
    '.tox', '.coverage', 'build', 'dist',
}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.rmvb'}
SUBTITLE_EXTENSIONS = {'.ass', '.srt'}
PREFERRED_LANG = 'SC'
