import platform
import re
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner


@dataclass
class GPUInfo:
    index: int
    vendor: str        # 'nvidia' | 'amd' | 'intel' | 'apple'
    name: str
    driver: str
    hwaccel: str       # FFmpeg hwaccel type: 'cuda' | 'd3d11va' | 'qsv'
    encoders: list[str]  # supported encoder names

    @property
    def label(self) -> str:
        return f"{self.vendor.upper()} #{self.index}: {self.name}"

    @property
    def value(self) -> str:
        return f"{self.index}:{self.hwaccel}"


_NVIDIA_ENCODERS = ['h264_nvenc', 'hevc_nvenc', 'av1_nvenc']
_AMD_ENCODERS = ['h264_amf', 'hevc_amf', 'av1_amf']
_INTEL_ENCODERS = ['h264_qsv', 'hevc_qsv', 'av1_qsv']
_MACOS_ENCODERS = ['h264_videotoolbox', 'hevc_videotoolbox', 'prores_videotoolbox']


class GPUDetector:
    def __init__(self, ffmpeg_runner: 'FFmpegRunner'):
        self._runner = ffmpeg_runner
        self._macos_gpus_cache: list[GPUInfo] | None = None

    def detect_all(self) -> list[GPUInfo]:
        gpus = []
        gpus.extend(self.detect_nvidia())
        if platform.system() == 'Darwin':
            gpus.extend(self._detect_macos_gpu())
        else:
            gpus.extend(self.detect_amd())
            gpus.extend(self.detect_intel())
        return gpus

    def detect_nvidia(self) -> list[GPUInfo]:
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=index,name,driver_version', '--format=csv,noheader'],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            if result.returncode == 0:
                gpus = []
                for line in result.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        idx = int(parts[0])
                        name = parts[1]
                        driver = parts[2]
                        encoders = [e for e in _NVIDIA_ENCODERS if self._runner.check_encoder(e)]
                        gpus.append(GPUInfo(idx, 'nvidia', name, driver, 'cuda', encoders))
                return gpus
        except Exception:
            pass
        return []

    def detect_amd(self) -> list[GPUInfo]:
        if platform.system() == 'Windows':
            return self._detect_windows_gpu(['AMD', 'ATI', 'RADEON'], 'amd', 'd3d11va', _AMD_ENCODERS)
        elif platform.system() == 'Linux':
            return self._detect_linux_gpu(['amd', 'ati', 'advanced micro devices'], 'amd', 'vaapi', _AMD_ENCODERS)
        elif platform.system() == 'Darwin':
            return [g for g in self._detect_macos_gpu() if g.vendor == 'amd']
        return []

    def detect_intel(self) -> list[GPUInfo]:
        if platform.system() == 'Windows':
            return self._detect_windows_gpu(['INTEL', 'INTEL(R)'], 'intel', 'qsv', _INTEL_ENCODERS)
        elif platform.system() == 'Linux':
            return self._detect_linux_gpu(['intel'], 'intel', 'vaapi', _INTEL_ENCODERS)
        elif platform.system() == 'Darwin':
            return [g for g in self._detect_macos_gpu() if g.vendor == 'intel']
        return []

    def _detect_windows_gpu(self, vendor_keywords: list[str], vendor_label: str,
                           hwaccel: str, encoders: list[str]) -> list[GPUInfo]:
        if platform.system() != 'Windows':
            return []
        gpu_lines = self._query_windows_gpus()
        if not gpu_lines:
            return []
        gpus = []
        idx = 0
        for line in gpu_lines:
            parts = line.split(',')
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            driver = parts[1].strip()
            if any(kw in name.upper() for kw in vendor_keywords):
                supported = [e for e in encoders if self._runner.check_encoder(e)]
                gpus.append(GPUInfo(idx, vendor_label, name, driver, hwaccel, supported))
                idx += 1
        return gpus

    def _query_windows_gpus(self) -> list[str]:
        try:
            result = subprocess.run(
                ['wmic', 'path', 'win32_VideoController', 'get', 'name,driverVersion', '/format:csv'],
                capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10
            )
            if result.returncode == 0:
                lines = []
                for line in result.stdout.strip().splitlines():
                    if not line.strip() or ',' not in line:
                        continue
                    parts = line.split(',')
                    if len(parts) < 3:
                        continue
                    lines.append(f"{parts[1].strip()},{parts[2].strip()}")
                if lines:
                    return lines
        except Exception:
            pass

        try:
            ps_cmd = [
                'powershell', '-NoProfile', '-Command',
                'Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | ConvertTo-Csv -NoTypeInformation'
            ]
            result = subprocess.run(
                ps_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=15
            )
            if result.returncode == 0:
                lines = []
                for i, line in enumerate(result.stdout.strip().splitlines()):
                    line = line.strip()
                    if i == 0 or not line or ',' not in line:
                        continue
                    parts = [p.strip('"') for p in line.split(',')]
                    if len(parts) >= 2:
                        lines.append(f"{parts[0]},{parts[1]}")
                if lines:
                    return lines
        except Exception:
            pass

        return []

    def _detect_macos_gpu(self) -> list[GPUInfo]:
        if self._macos_gpus_cache is not None:
            return self._macos_gpus_cache
        try:
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType'],
                capture_output=True, text=True, encoding='utf-8',
                errors='ignore', timeout=15,
            )
            if result.returncode != 0:
                self._macos_gpus_cache = []
                return []
        except Exception:
            self._macos_gpus_cache = []
            return []

        gpus = []
        idx = 0
        for line in result.stdout.splitlines():
            if 'Chipset Model:' in line:
                chipset = line.split(':', 1)[1].strip()
                if 'AMD' in chipset or 'Radeon' in chipset:
                    vendor = 'amd'
                elif 'Intel' in chipset:
                    vendor = 'intel'
                else:
                    vendor = 'apple'
                supported = [e for e in _MACOS_ENCODERS if self._runner.check_encoder(e)]
                gpus.append(GPUInfo(idx, vendor, chipset, 'macos', 'videotoolbox', supported))
                idx += 1

        self._macos_gpus_cache = gpus
        return gpus

    def _detect_linux_gpu(self, vendor_keywords: list[str], vendor_label: str,
                          hwaccel: str, encoders: list[str]) -> list[GPUInfo]:
        try:
            result = subprocess.run(
                ['lspci', '-nn'],
                capture_output=True, text=True, encoding='utf-8',
                errors='ignore', timeout=10,
            )
            if result.returncode != 0:
                return []
        except Exception:
            return []

        gpus = []
        idx = 0
        for line in result.stdout.splitlines():
            if not any(kw in line.lower() for kw in vendor_keywords):
                continue
            if not any(k in line.lower() for k in ['vga', '3d', 'display', 'compatible']):
                continue
            parts = line.split(':', 1)
            if len(parts) < 2:
                continue
            name = re.sub(r'\s*\[.*?\]\s*$', '', parts[1]).strip()
            name = re.sub(r'\s*\(rev\s+\w+\)\s*$', '', name).strip()
            supported = [e for e in encoders if self._runner.check_encoder(e)]
            gpus.append(GPUInfo(idx, vendor_label, name, 'linux', hwaccel, supported))
            idx += 1
        return gpus


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