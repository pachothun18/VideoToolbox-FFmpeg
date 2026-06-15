import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner

from app.core.gpu.base import GPUInfo, _NVIDIA_ENCODERS, _AMD_ENCODERS, _INTEL_ENCODERS, _detect_nvidia_smi, _check_encoders


_PNP_VEN_MAP = {
    0x10DE: 'nvidia',
    0x1002: 'amd',
    0x1022: 'amd',
    0x8086: 'intel',
    0x8087: 'intel',
}

class WindowsGPUDetector:
    def __init__(self, ffmpeg_runner: 'FFmpegRunner'):
        self._runner = ffmpeg_runner
        self._gpu_entries_cache: list[dict] | None = None

    # ── public API ────────────────────────────────────────────

    def detect_nvidia(self) -> list[GPUInfo]:
        gpus = _detect_nvidia_smi(self._runner)
        if gpus:
            return gpus
        return self._detect_by_pnp('nvidia', 'cuda', _NVIDIA_ENCODERS,
                                    ['NVIDIA', 'GEFORCE', 'QUADRO', 'TITAN', 'TESLA'])

    def detect_amd(self) -> list[GPUInfo]:
        return self._detect_by_pnp('amd', 'd3d11va', _AMD_ENCODERS,
                                    ['AMD', 'ATI', 'RADEON', 'FIREPRO'])

    def detect_intel(self) -> list[GPUInfo]:
        return self._detect_by_pnp('intel', 'qsv', _INTEL_ENCODERS,
                                    ['INTEL', 'INTEL(R)'])

    # ── WMI / Registry data source ────────────────────────────

    def _query_powershell(self) -> list[dict] | None:
        try:
            ps_cmd = [
                'powershell', '-NoProfile', '-Command',
                'Get-CimInstance Win32_VideoController | '
                'Select-Object Name,DriverVersion,PNPDeviceID,AdapterCompatibility | '
                'ConvertTo-Csv -NoTypeInformation'
            ]
            result = subprocess.run(
                ps_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15
            )
            if result.returncode != 0:
                return None
            entries = []
            for i, line in enumerate(result.stdout.strip().splitlines()):
                line = line.strip()
                if i == 0 or not line or ',' not in line:
                    continue
                parts = [p.strip('"') for p in line.split(',')]
                if len(parts) < 4:
                    continue
                name = parts[0].strip()
                driver = parts[1].strip()
                pnp_id = parts[2].strip()
                compat = parts[3].strip()
                if name:
                    entries.append({
                        'name': name,
                        'name_upper': name.upper(),
                        'driver': driver,
                        'pnp_id': pnp_id,
                        'compat': compat.upper(),
                    })
            return entries if entries else None
        except Exception:
            return None

    def _query_registry(self) -> list[dict] | None:
        try:
            import winreg
        except ImportError:
            return None
        try:
            key_path = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            entries = []
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    i += 1
                except OSError:
                    break
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                except OSError:
                    continue
                try:
                    desc = winreg.QueryValueEx(subkey, 'DriverDesc')[0]
                except FileNotFoundError:
                    winreg.CloseKey(subkey)
                    continue
                if not isinstance(desc, str) or not desc.strip():
                    winreg.CloseKey(subkey)
                    continue
                driver = ''
                try:
                    driver = winreg.QueryValueEx(subkey, 'DriverVersion')[0]
                except FileNotFoundError:
                    pass
                pnp_id = ''
                try:
                    pnp_id = winreg.QueryValueEx(subkey, 'MatchingDeviceId')[0]
                except FileNotFoundError:
                    pass
                compat = ''
                try:
                    compat = winreg.QueryValueEx(subkey, 'ProviderName')[0]
                except FileNotFoundError:
                    pass
                winreg.CloseKey(subkey)
                entries.append({
                    'name': desc.strip(),
                    'name_upper': desc.upper(),
                    'driver': str(driver).strip() if driver else '',
                    'pnp_id': str(pnp_id).strip() if pnp_id else '',
                    'compat': str(compat).upper().strip() if compat else '',
                })
            winreg.CloseKey(key)
            return entries if entries else None
        except Exception:
            return None

    def _get_all_entries(self) -> list[dict]:
        if self._gpu_entries_cache is not None:
            return self._gpu_entries_cache
        for method in [self._query_powershell, self._query_registry]:
            result = method()
            if result:
                self._gpu_entries_cache = result
                return result
        self._gpu_entries_cache = []
        return []

    # ── vendor helpers ────────────────────────────────────────

    @staticmethod
    def _parse_pnp_vendor(pnp_id: str) -> str | None:
        m = re.search(r'VEN_([0-9A-Fa-f]+)', pnp_id)
        if m:
            vid = int(m.group(1), 16)
            return _PNP_VEN_MAP.get(vid)
        return None

    def _detect_by_pnp(self, vendor_label: str, hwaccel: str,
                       encoders: list[str], name_keywords: list[str]) -> list[GPUInfo]:
        entries = self._get_all_entries()
        if not entries:
            return []
        gpus = []
        idx = 0
        for e in entries:
            vendor_from_pnp = self._parse_pnp_vendor(e['pnp_id'])
            if vendor_from_pnp == vendor_label:
                pass
            elif vendor_from_pnp is None:
                if not any(kw in e['name_upper'] for kw in name_keywords):
                    continue
            else:
                continue
            supported = _check_encoders(self._runner, encoders)
            gpus.append(GPUInfo(idx, vendor_label, e['name'],
                                e['driver'] or 'unknown', hwaccel, supported))
            idx += 1
        return gpus
