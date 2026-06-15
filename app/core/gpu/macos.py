import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner

from app.core.gpu.base import GPUInfo, _MACOS_ENCODERS, _check_encoders


class MacOSGPUDetector:
    def __init__(self, ffmpeg_runner: 'FFmpegRunner'):
        self._runner = ffmpeg_runner
        self._cache: list[GPUInfo] | None = None

    def detect_all(self) -> list[GPUInfo]:
        if self._cache is not None:
            return self._cache

        try:
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType'],
                capture_output=True, text=True, encoding='utf-8',
                errors='ignore', timeout=15,
            )
            if result.returncode != 0:
                self._cache = []
                return []
        except Exception:
            self._cache = []
            return []

        gpus = []
        idx = 0
        for line in result.stdout.splitlines():
            if not line.startswith('    ') or not line.rstrip().endswith(':'):
                continue
            name = line.strip()[:-1].strip()
            if not name or name == 'Graphics/Displays':
                continue
            if 'AMD' in name or 'Radeon' in name:
                vendor = 'amd'
            elif 'Intel' in name:
                vendor = 'intel'
            else:
                vendor = 'apple'
            supported = _check_encoders(self._runner, _MACOS_ENCODERS)
            gpus.append(GPUInfo(idx, vendor, name, 'macos', 'videotoolbox', supported))
            idx += 1

        self._cache = gpus
        return gpus
