import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner

from app.core.gpu.base import GPUInfo
from app.core.gpu.windows import WindowsGPUDetector
from app.core.gpu.linux import LinuxGPUDetector
from app.core.gpu.macos import MacOSGPUDetector


class GPUDetector:
    def __init__(self, ffmpeg_runner: 'FFmpegRunner'):
        self._runner = ffmpeg_runner
        self._win = WindowsGPUDetector(ffmpeg_runner)
        self._lin = LinuxGPUDetector(ffmpeg_runner)
        self._mac = MacOSGPUDetector(ffmpeg_runner)

    def detect_all(self) -> list[GPUInfo]:
        gpus = []
        if platform.system() != 'Darwin':
            gpus.extend(self.detect_nvidia())
        if platform.system() == 'Darwin':
            gpus.extend(self._mac.detect_all())
        else:
            gpus.extend(self.detect_amd())
            gpus.extend(self.detect_intel())
        if platform.system() == 'Linux' and not gpus:
            gpus.extend(self._lin.detect_fallback())
        return gpus

    def detect_nvidia(self) -> list[GPUInfo]:
        if platform.system() == 'Windows':
            return self._win.detect_nvidia()
        elif platform.system() == 'Linux':
            return self._lin.detect_nvidia()
        return []

    def detect_amd(self) -> list[GPUInfo]:
        if platform.system() == 'Windows':
            return self._win.detect_amd()
        elif platform.system() == 'Linux':
            return self._lin.detect_amd()
        elif platform.system() == 'Darwin':
            return [g for g in self._mac.detect_all() if g.vendor == 'amd']
        return []

    def detect_intel(self) -> list[GPUInfo]:
        if platform.system() == 'Windows':
            return self._win.detect_intel()
        elif platform.system() == 'Linux':
            return self._lin.detect_intel()
        elif platform.system() == 'Darwin':
            return [g for g in self._mac.detect_all() if g.vendor == 'intel']
        return []


# ── standalone convenience functions (backward compat) ──────


def get_nvidia_gpu_info():
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    gpus = detector.detect_nvidia()
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def get_all_nvidia_gpus() -> list[GPUInfo]:
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    return detector.detect_nvidia()


def get_amd_gpu_info():
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    gpus = detector.detect_amd()
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def get_all_amd_gpus() -> list[GPUInfo]:
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    return detector.detect_amd()


def get_intel_gpu_info():
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    gpus = detector.detect_intel()
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def get_all_intel_gpus() -> list[GPUInfo]:
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    return detector.detect_intel()


def detect_all_gpus() -> list[GPUInfo]:
    from app.core.ffmpeg import FFmpegRunner
    runner = FFmpegRunner('', '')
    detector = GPUDetector(runner)
    return detector.detect_all()
