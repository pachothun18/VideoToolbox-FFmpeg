import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner

from app.core.gpu.base import GPUInfo, _AMD_ENCODERS, _INTEL_ENCODERS, _detect_nvidia_smi, _check_encoders


class LinuxGPUDetector:
    def __init__(self, ffmpeg_runner: 'FFmpegRunner'):
        self._runner = ffmpeg_runner

    def detect_nvidia(self) -> list[GPUInfo]:
        return _detect_nvidia_smi(self._runner)

    def detect_amd(self) -> list[GPUInfo]:
        return self._detect_lspci(['amd', 'ati', 'advanced micro devices'],
                                   'amd', 'vaapi', _AMD_ENCODERS)

    def detect_intel(self) -> list[GPUInfo]:
        return self._detect_lspci(['intel'],
                                   'intel', 'vaapi', _INTEL_ENCODERS)

    def detect_fallback(self) -> list[GPUInfo]:
        vaapi_encoders = ['h264_vaapi', 'hevc_vaapi']
        supported = [e for e in vaapi_encoders if self._runner.check_encoder(e)]
        if supported:
            return [GPUInfo(0, 'intel', 'Linux GPU (via VAAPI)',
                            'unknown', 'vaapi', supported)]
        return []

    def _detect_lspci(self, vendor_keywords: list[str], vendor_label: str,
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
            supported = _check_encoders(self._runner, encoders)
            gpus.append(GPUInfo(idx, vendor_label, name,
                                'linux', hwaccel, supported))
            idx += 1
        return gpus
