import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner


@dataclass
class GPUInfo:
    index: int
    vendor: str
    name: str
    driver: str
    hwaccel: str
    encoders: list[str]

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


def _detect_nvidia_smi(runner: 'FFmpegRunner') -> list[GPUInfo]:
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,driver_version', '--format=csv,noheader'],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=15,
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(',', 2)]
                if len(parts) >= 3:
                    idx = int(parts[0])
                    name = parts[1]
                    driver = parts[2]
                    encoders = [e for e in _NVIDIA_ENCODERS if runner.check_encoder(e)]
                    gpus.append(GPUInfo(idx, 'nvidia', name, driver, 'cuda', encoders))
            return gpus
    except Exception:
        pass
    return []


def _check_encoders(runner: 'FFmpegRunner', encoders: list[str]) -> list[str]:
    return [e for e in encoders if runner.check_encoder(e)]
