import platform
import subprocess
from dataclasses import dataclass


@dataclass
class GPUInfo:
    index: int
    vendor: str        # 'nvidia' | 'amd' | 'intel'
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


def get_nvidia_gpu_info():
    """Legacy: return (name, driver) of first NVIDIA GPU."""
    gpus = get_all_nvidia_gpus()
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def get_all_nvidia_gpus() -> list[GPUInfo]:
    """Query nvidia-smi for all NVIDIA GPUs."""
    from app.core.ffmpeg import check_encoder_support
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
                    encoders = [e for e in _NVIDIA_ENCODERS if check_encoder_support(e)]
                    gpus.append(GPUInfo(idx, 'nvidia', name, driver, 'cuda', encoders))
            return gpus
    except Exception:
        pass
    return []


def _get_gpu_info_by_vendor(vendor_keywords):
    """Legacy: return (name, driver) of first matching GPU via WMI."""
    gpus = _get_all_gpus_by_vendor(vendor_keywords)
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def _get_all_gpus_by_vendor(vendor_keywords, vendor_label: str, hwaccel: str, encoders: list[str]) -> list[GPUInfo]:
    """Query Windows GPU info for all GPUs matching vendor keywords."""
    if platform.system() != 'Windows':
        return []
    from app.core.ffmpeg import check_encoder_support
    gpu_lines = _query_windows_gpus()
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
            supported = [e for e in encoders if check_encoder_support(e)]
            gpus.append(GPUInfo(idx, vendor_label, name, driver, hwaccel, supported))
            idx += 1
    return gpus


def _query_windows_gpus() -> list[str]:
    """Query GPU info from Windows via WMI. Tries wmic first, falls back to PowerShell."""
    # Try wmic first (legacy Windows)
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

    # Fallback: PowerShell Get-CimInstance (available on Windows 10/11)
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
                # Parse CSV: remove surrounding quotes if present
                parts = [p.strip('"') for p in line.split(',')]
                if len(parts) >= 2:
                    lines.append(f"{parts[0]},{parts[1]}")
            if lines:
                return lines
    except Exception:
        pass

    return []


def get_amd_gpu_info():
    """Legacy: return (name, driver) of first AMD GPU."""
    gpus = get_all_amd_gpus()
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def get_all_amd_gpus() -> list[GPUInfo]:
    return _get_all_gpus_by_vendor(['AMD', 'ATI', 'RADEON'], 'amd', 'd3d11va', _AMD_ENCODERS)


def get_intel_gpu_info():
    """Legacy: return (name, driver) of first Intel GPU."""
    gpus = get_all_intel_gpus()
    if gpus:
        return gpus[0].name, gpus[0].driver
    return None, None


def get_all_intel_gpus() -> list[GPUInfo]:
    return _get_all_gpus_by_vendor(['INTEL', 'INTEL(R)'], 'intel', 'qsv', _INTEL_ENCODERS)


def detect_all_gpus() -> list[GPUInfo]:
    """Detect all available GPUs across vendors. Order: NVIDIA > AMD > Intel.

    Each vendor's GPU indices are vendor-local (not globally numbered):
    - NVIDIA: index comes from nvidia-smi (system PCI index, e.g. 0, 1)
    - AMD/Intel: index is auto-incremented within that vendor (0, 1, ...)

    The GPUInfo.value format is "index:hwaccel" — the hwaccel type disambiguates
    which vendor namespace the index belongs to, preventing collisions in
    multi-vendor setups (e.g. NVIDIA #0 vs AMD #0).
    """
    gpus = []
    gpus.extend(get_all_nvidia_gpus())
    gpus.extend(get_all_amd_gpus())
    gpus.extend(get_all_intel_gpus())
    return gpus
