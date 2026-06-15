from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ffmpeg import FFmpegRunner

_PIX_FMT_TABLE = {
    ('8bit',  '420'): 'yuv420p',
    ('8bit',  '422'): 'yuv422p',
    ('8bit',  '444'): 'yuv444p',
    ('10bit', '420'): 'yuv420p10le',
    ('10bit', '422'): 'yuv422p10le',
    ('10bit', '444'): 'yuv444p10le',
}

_NV_PIX_FMT_TABLE = {
    ('8bit',  '420'): 'yuv420p',
    ('8bit',  '422'): 'yuv422p',
    ('8bit',  '444'): 'yuv444p',
    ('10bit', '420'): 'p010le',
    ('10bit', '422'): 'yuv422p10le',
    ('10bit', '444'): 'yuv444p16le',
}


def _nv_pix_fmt(depth: str, chroma: str, pix_fmt_10bit: str | None) -> str | None:
    if depth == '10bit' and chroma == '420':
        return pix_fmt_10bit
    return _NV_PIX_FMT_TABLE.get((depth, chroma))


_VT_PIX_FMT_TABLE = {
    ('8bit',  '420'): 'nv12',
    ('8bit',  '422'): 'nv12',
    ('8bit',  '444'): 'nv12',
    ('10bit', '420'): 'p010',
    ('10bit', '422'): 'p010',
    ('10bit', '444'): 'p010',
}


_VT_H264_PROFILES = {
    ('8bit',  '420'): 'high',
    ('8bit',  '422'): None,
    ('8bit',  '444'): None,
}

_VT_HEVC_PROFILES = {
    ('8bit',  '420'): 'main',
    ('8bit',  '422'): None,
    ('8bit',  '444'): None,
    ('10bit', '420'): 'main10',
    ('10bit', '422'): None,
    ('10bit', '444'): None,
}


_HEVC_SW_PROFILES = {
    ('8bit',  '420'): None,
    ('8bit',  '422'): None,
    ('8bit',  '444'): 'main444',
    ('10bit', '420'): 'main10',
    ('10bit', '422'): 'main422-10',
    ('10bit', '444'): 'main444-10',
}

_HEVC_NVENC_PROFILES = {
    ('8bit',  '420'): None,
    ('8bit',  '422'): 'rext',
    ('8bit',  '444'): 'rext',
    ('10bit', '420'): 'main10',
    ('10bit', '422'): 'rext',
    ('10bit', '444'): 'rext',
}

_HEVC_AMF_PROFILES = {
    ('8bit',  '420'): None,
    ('8bit',  '422'): 'rext',
    ('8bit',  '444'): 'rext',
    ('10bit', '420'): 'main10',
    ('10bit', '422'): 'rext',
    ('10bit', '444'): 'rext',
}

_H264_PROFILES = {
    ('8bit',  '420'): None,
    ('8bit',  '422'): 'high422',
    ('8bit',  '444'): 'high444',
    ('10bit', '420'): 'high10',
    ('10bit', '422'): 'high422',
    ('10bit', '444'): 'high444',
}

_AV1_PROFILES = {
    ('8bit',  '420'): None,
    ('8bit',  '422'): None,
    ('8bit',  '444'): 'high',
    ('10bit', '420'): 'main',
    ('10bit', '422'): None,
    ('10bit', '444'): 'professional',
}

_NONE_MAP = {}


@dataclass
class EncoderProfile:
    name: str
    label: str
    use_gpu: bool
    hwaccel: str | None
    default_pix_fmt: str
    supports_10bit: bool
    pix_fmt_10bit: str | None
    quality_param: str
    rate_control: list[str] = field(default_factory=list)
    _profile_map: dict = field(default_factory=dict, repr=False)

    @property
    def is_nvenc(self):
        return 'nvenc' in self.name

    @property
    def is_amf(self):
        return 'amf' in self.name

    @property
    def is_vaapi(self):
        return 'vaapi' in self.name

    @property
    def is_videotoolbox(self):
        return 'videotoolbox' in self.name

    def get_pix_fmt(self, depth: str, chroma: str) -> str | None:
        if not self.supports_10bit and depth == '10bit':
            return None
        if self.is_nvenc or self.is_amf or self.is_vaapi:
            return _nv_pix_fmt(depth, chroma, self.pix_fmt_10bit)
        if self.is_videotoolbox:
            return _VT_PIX_FMT_TABLE.get((depth, chroma))
        return _PIX_FMT_TABLE.get((depth, chroma))

    def get_profile(self, depth: str, chroma: str) -> str | None:
        return self._profile_map.get((depth, chroma))


H264_NVENC = EncoderProfile(
    name='h264_nvenc', label='h264_nvenc (H.264)',
    use_gpu=True, hwaccel='cuda',
    default_pix_fmt='yuv420p', supports_10bit=False, pix_fmt_10bit=None,
    quality_param='cq', rate_control=['-rc', 'vbr'],
    _profile_map=_H264_PROFILES,
)

HEVC_NVENC = EncoderProfile(
    name='hevc_nvenc', label='hevc_nvenc (H.265)',
    use_gpu=True, hwaccel='cuda',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='cq', rate_control=['-rc', 'vbr'],
    _profile_map=_HEVC_NVENC_PROFILES,
)

LIBX264 = EncoderProfile(
    name='libx264', label='libx264 (H.264)',
    use_gpu=False, hwaccel=None,
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='yuv420p10le',
    quality_param='crf', rate_control=[],
    _profile_map=_H264_PROFILES,
)

LIBX265 = EncoderProfile(
    name='libx265', label='libx265 (H.265)',
    use_gpu=False, hwaccel=None,
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='yuv420p10le',
    quality_param='crf', rate_control=[],
    _profile_map=_HEVC_SW_PROFILES,
)

LIBSVTAV1 = EncoderProfile(
    name='libsvtav1', label='libsvtav1 (AV1)',
    use_gpu=False, hwaccel=None,
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='yuv420p10le',
    quality_param='crf', rate_control=[],
    _profile_map=_AV1_PROFILES,
)

LIBVPX_VP9 = EncoderProfile(
    name='libvpx-vp9', label='libvpx-vp9 (VP9)',
    use_gpu=False, hwaccel=None,
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='yuv420p10le',
    quality_param='crf', rate_control=[],
    _profile_map=_NONE_MAP,
)

H264_AMF = EncoderProfile(
    name='h264_amf', label='h264_amf (H.264)',
    use_gpu=True, hwaccel='d3d11va',
    default_pix_fmt='yuv420p', supports_10bit=False, pix_fmt_10bit=None,
    quality_param='cq', rate_control=['-rc', 'qvbr'],
    _profile_map=_H264_PROFILES,
)

HEVC_AMF = EncoderProfile(
    name='hevc_amf', label='hevc_amf (H.265)',
    use_gpu=True, hwaccel='d3d11va',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='cq', rate_control=['-rc', 'qvbr'],
    _profile_map=_HEVC_AMF_PROFILES,
)

AV1_AMF = EncoderProfile(
    name='av1_amf', label='av1_amf (AV1)',
    use_gpu=True, hwaccel='d3d11va',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='cq', rate_control=['-rc', 'qvbr'],
    _profile_map=_AV1_PROFILES,
)

H264_QSV = EncoderProfile(
    name='h264_qsv', label='h264_qsv (H.264)',
    use_gpu=True, hwaccel='qsv',
    default_pix_fmt='yuv420p', supports_10bit=False, pix_fmt_10bit=None,
    quality_param='global_quality', rate_control=[],
    _profile_map=_H264_PROFILES,
)

HEVC_QSV = EncoderProfile(
    name='hevc_qsv', label='hevc_qsv (H.265)',
    use_gpu=True, hwaccel='qsv',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='global_quality', rate_control=[],
    _profile_map=_HEVC_NVENC_PROFILES,
)

AV1_QSV = EncoderProfile(
    name='av1_qsv', label='av1_qsv (AV1)',
    use_gpu=True, hwaccel='qsv',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='global_quality', rate_control=[],
    _profile_map=_AV1_PROFILES,
)

H264_VAAPI = EncoderProfile(
    name='h264_vaapi', label='h264_vaapi (H.264)',
    use_gpu=True, hwaccel='vaapi',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='yuv420p10le',
    quality_param='qp', rate_control=[],
    _profile_map=_H264_PROFILES,
)

HEVC_VAAPI = EncoderProfile(
    name='hevc_vaapi', label='hevc_vaapi (H.265)',
    use_gpu=True, hwaccel='vaapi',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='qp', rate_control=[],
    _profile_map=_HEVC_NVENC_PROFILES,
)

H264_VIDEOTOOLBOX = EncoderProfile(
    name='h264_videotoolbox', label='h264_videotoolbox (H.264)',
    use_gpu=True, hwaccel='videotoolbox',
    default_pix_fmt='nv12', supports_10bit=False, pix_fmt_10bit=None,
    quality_param='quality', rate_control=[],
    _profile_map=_VT_H264_PROFILES,
)

HEVC_VIDEOTOOLBOX = EncoderProfile(
    name='hevc_videotoolbox', label='hevc_videotoolbox (H.265)',
    use_gpu=True, hwaccel='videotoolbox',
    default_pix_fmt='nv12', supports_10bit=True, pix_fmt_10bit='p010',
    quality_param='quality', rate_control=[],
    _profile_map=_VT_HEVC_PROFILES,
)

ALL_PROFILES = [H264_NVENC, HEVC_NVENC, H264_AMF, HEVC_AMF, AV1_AMF,
                H264_QSV, HEVC_QSV, AV1_QSV,
                H264_VAAPI, HEVC_VAAPI,
                H264_VIDEOTOOLBOX, HEVC_VIDEOTOOLBOX,
                LIBX264, LIBX265, LIBSVTAV1, LIBVPX_VP9]
GPU_PROFILES = [p for p in ALL_PROFILES if p.use_gpu]
CPU_PROFILES = [p for p in ALL_PROFILES if not p.use_gpu]


class EncoderRegistry:
    def __init__(self, ffmpeg_runner: 'FFmpegRunner'):
        self._runner = ffmpeg_runner
        self._profiles: dict[str, EncoderProfile] = {}
        self._register_defaults()

    def _register_defaults(self):
        for profile in ALL_PROFILES:
            self._profiles[profile.name] = profile

    def get(self, name: str) -> EncoderProfile | None:
        return self._profiles.get(name)

    def get_available_gpu(self) -> list[EncoderProfile]:
        return [p for p in GPU_PROFILES if self._runner.check_encoder(p.name)]

    def get_all_cpu(self) -> list[EncoderProfile]:
        return CPU_PROFILES

    def auto_select(self, video_path: str, force_cpu: bool = False,
                    preferred_hwaccel: str | None = None):
        from app.commands.bitdepth import _parse_pix_fmt
        codec, pix_fmt = self._runner.get_video_info(video_path)
        in_depth, in_chroma = _parse_pix_fmt(pix_fmt)

        vf = None

        if force_cpu:
            encoder = LIBX264
            out_depth = '8bit'
            out_chroma = '420'
            if in_depth == '10bit':
                vf = f'format={encoder.get_pix_fmt(out_depth, out_chroma)}'
            return encoder, encoder.get_pix_fmt(out_depth, out_chroma), \
                encoder.get_profile(out_depth, out_chroma), vf, \
                f"CPU (libx264, {out_depth} {out_chroma})"

        if in_chroma == '422':
            out_chroma = '420'
            downgrade_msg = f"原视频{in_chroma} GPU不支持，降为{out_chroma}"
        else:
            out_chroma = in_chroma
            downgrade_msg = ''

        has_h264_nv = self._runner.check_encoder('h264_nvenc')
        has_hevc_nv = self._runner.check_encoder('hevc_nvenc')
        has_h264_amf = self._runner.check_encoder('h264_amf')
        has_hevc_amf = self._runner.check_encoder('hevc_amf')
        has_h264_qsv = self._runner.check_encoder('h264_qsv')
        has_hevc_qsv = self._runner.check_encoder('hevc_qsv')
        has_h264_va = self._runner.check_encoder('h264_vaapi')
        has_hevc_va = self._runner.check_encoder('hevc_vaapi')
        has_h264_vt = self._runner.check_encoder('h264_videotoolbox')
        has_hevc_vt = self._runner.check_encoder('hevc_videotoolbox')

        _groups = [
            ('cuda',          H264_NVENC,       HEVC_NVENC,       has_h264_nv, has_hevc_nv),
            ('vaapi',         H264_VAAPI,       HEVC_VAAPI,       has_h264_va, has_hevc_va),
            ('d3d11va',       H264_AMF,         HEVC_AMF,         has_h264_amf, has_hevc_amf),
            ('qsv',           H264_QSV,         HEVC_QSV,         has_h264_qsv, has_hevc_qsv),
            ('videotoolbox',  H264_VIDEOTOOLBOX, HEVC_VIDEOTOOLBOX, has_h264_vt, has_hevc_vt),
        ]

        if preferred_hwaccel:
            idx = next((i for i, g in enumerate(_groups) if g[0] == preferred_hwaccel), -1)
            if idx > 0:
                _groups.insert(0, _groups.pop(idx))

        encoder = LIBX264
        out_depth = '8bit'
        if in_depth == '10bit':
            for hw, h264_enc, hevc_enc, has_h264, has_hevc in _groups:
                if has_hevc:
                    encoder = hevc_enc
                    out_depth = '10bit'
                    break
            else:
                out_chroma = '420'
        else:
            out_depth = '8bit'
            for hw, h264_enc, hevc_enc, has_h264, has_hevc in _groups:
                if has_h264 and out_chroma == '420':
                    encoder = h264_enc
                    break
                if has_hevc and out_chroma in ('420', '444'):
                    encoder = hevc_enc
                    break
                if has_hevc:
                    encoder = hevc_enc
                    break

        out_fmt = encoder.get_pix_fmt(out_depth, out_chroma)
        profile = encoder.get_profile(out_depth, out_chroma)

        if pix_fmt != out_fmt:
            vf = f'format={out_fmt}'

        parts = [f"{'GPU' if encoder.use_gpu else 'CPU'} ({encoder.name.split('_')[1].upper() if '_' in encoder.name else encoder.name}, {out_depth} {out_chroma})"]
        if downgrade_msg:
            parts.append(downgrade_msg)

        return encoder, out_fmt, profile, vf, ' '.join(parts)


def get_profile(name: str) -> EncoderProfile | None:
    for p in ALL_PROFILES:
        if p.name == name:
            return p
    return None


def get_available_gpu_profiles():
    from app import _registry
    return _registry.get_available_gpu()


def auto_select_encoder(video_path: str, force_cpu: bool = False,
                        preferred_hwaccel: str | None = None):
    from app import _registry
    return _registry.auto_select(video_path, force_cpu, preferred_hwaccel)