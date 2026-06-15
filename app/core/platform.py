"""Platform detection and platform-specific configuration for cross-platform support."""

import platform
import shutil
from pathlib import Path

_OS = platform.system()


def is_windows() -> bool:
    return _OS == 'Windows'


def is_linux() -> bool:
    return _OS == 'Linux'


def is_macos() -> bool:
    return _OS == 'Darwin'


def get_platform_name() -> str:
    return _OS


def resolve_ffmpeg(base_dir: Path) -> str:
    """Resolve ffmpeg executable path based on current platform.

    Linux:  system PATH ffmpeg → bundled ffmpeg (no .exe) → 'ffmpeg'
    Windows: bundled ffmpeg.exe → system PATH ffmpeg → 'ffmpeg'
    """
    if is_windows():
        bundled = base_dir / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)
        return shutil.which("ffmpeg") or "ffmpeg"
    else:
        bundled = base_dir / "ffmpeg"
        if bundled.exists():
            return str(bundled)
        return shutil.which("ffmpeg") or "ffmpeg"


def resolve_ffprobe(base_dir: Path) -> str:
    """Resolve ffprobe executable path based on current platform.

    Linux:  system PATH ffprobe → bundled ffprobe (no .exe) → 'ffprobe'
    Windows: bundled ffprobe.exe → system PATH ffprobe → 'ffprobe'
    """
    if is_windows():
        bundled = base_dir / "ffprobe.exe"
        if bundled.exists():
            return str(bundled)
        return shutil.which("ffprobe") or "ffprobe"
    else:
        bundled = base_dir / "ffprobe"
        if bundled.exists():
            return str(bundled)
        return shutil.which("ffprobe") or "ffprobe"


def get_supported_hwaccel_types() -> list[str]:
    """Return hardware acceleration types supported on the current platform."""
    if is_windows():
        return ['cuda', 'd3d11va', 'qsv']
    elif is_macos():
        return ['videotoolbox']
    else:
        return ['cuda', 'vaapi']


def is_hwaccel_supported(hwaccel: str | None) -> bool:
    """Check if a given hwaccel type is supported on the current platform."""
    if hwaccel is None:
        return True
    return hwaccel in get_supported_hwaccel_types()
