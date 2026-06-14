from dataclasses import dataclass, field

_PIX_FMT_TABLE = {
    ('8bit',  '420'): 'yuv420p',
    ('8bit',  '422'): 'yuv422p',
    ('8bit',  '444'): 'yuv444p',
    ('10bit', '420'): 'yuv420p10le',
    ('10bit', '422'): 'yuv422p10le',
    ('10bit', '444'): 'yuv444p10le',
}

# NVENC pixel formats — must use chroma-explicit names (e.g. yuv444p16le, not p016le)
# so the format filter actually upsamples chroma from the source.
_NV_PIX_FMT_TABLE = {
    ('8bit',  '420'): 'yuv420p',
    ('8bit',  '422'): 'yuv422p',
    ('8bit',  '444'): 'yuv444p',
    ('10bit', '420'): 'p010le',        # NVENC 10bit 420 always uses p010le
    ('10bit', '422'): 'yuv422p10le',
    ('10bit', '444'): 'yuv444p16le',   # explicit 4:4:4 → filter will upsample
}


def _nv_pix_fmt(depth: str, chroma: str, pix_fmt_10bit: str | None) -> str | None:
    if depth == '10bit' and chroma == '420':
        return pix_fmt_10bit  # p010le
    return _NV_PIX_FMT_TABLE.get((depth, chroma))


# FFmpeg -profile:v values keyed by (depth, chroma)
# Software HEVC (libx265) — full named profiles
_HEVC_SW_PROFILES = {
    ('8bit',  '420'): None,
    ('8bit',  '422'): None,
    ('8bit',  '444'): 'main444',
    ('10bit', '420'): 'main10',
    ('10bit', '422'): 'main422-10',
    ('10bit', '444'): 'main444-10',
}

# NVENC HEVC — hardware encoder only accepts main / main10 / rext
_HEVC_NVENC_PROFILES = {
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
    hwaccel: str | None                # 'cuda' or None
    default_pix_fmt: str               # 'yuv420p'
    supports_10bit: bool
    pix_fmt_10bit: str | None          # NVENC uses 'p010le'; CPU uses 'yuv420p10le'
    quality_param: str                 # 'crf' or 'cq'
    rate_control: list[str] = field(default_factory=list)
    _profile_map: dict = field(default_factory=dict, repr=False)

    @property
    def is_nvenc(self):
        return 'nvenc' in self.name

    @property
    def is_amf(self):
        return 'amf' in self.name

    def get_pix_fmt(self, depth: str, chroma: str) -> str | None:
        if not self.supports_10bit and depth == '10bit':
            return None
        if self.is_nvenc or self.is_amf:
            return _nv_pix_fmt(depth, chroma, self.pix_fmt_10bit)
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

# AMD AMF profiles
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
    _profile_map=_HEVC_NVENC_PROFILES,
)

AV1_AMF = EncoderProfile(
    name='av1_amf', label='av1_amf (AV1)',
    use_gpu=True, hwaccel='d3d11va',
    default_pix_fmt='yuv420p', supports_10bit=True, pix_fmt_10bit='p010le',
    quality_param='cq', rate_control=['-rc', 'qvbr'],
    _profile_map=_AV1_PROFILES,
)

# Intel QSV profiles
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

ALL_PROFILES = [H264_NVENC, HEVC_NVENC, H264_AMF, HEVC_AMF, AV1_AMF,
                H264_QSV, HEVC_QSV, AV1_QSV,
                LIBX264, LIBX265, LIBSVTAV1, LIBVPX_VP9]
GPU_PROFILES = [p for p in ALL_PROFILES if p.use_gpu]
CPU_PROFILES = [p for p in ALL_PROFILES if not p.use_gpu]


def get_profile(name: str) -> EncoderProfile | None:
    for p in ALL_PROFILES:
        if p.name == name:
            return p
    return None


def get_available_gpu_profiles():
    from app.core.ffmpeg import check_encoder_support
    return [p for p in GPU_PROFILES if check_encoder_support(p.name)]


def _parse_pix_fmt(pix_fmt: str | None) -> tuple[str, str]:
    """Return (depth, chroma) from a pixel format string."""
    if not pix_fmt:
        return '8bit', '420'
    if pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le',
                   'p010le', 'p016le'):
        depth = '10bit'
    else:
        depth = '8bit'
    fmt_lower = pix_fmt.lower()
    if '444' in fmt_lower:
        chroma = '444'
    elif '422' in fmt_lower:
        chroma = '422'
    else:
        chroma = '420'
    return depth, chroma


def auto_select_encoder(video_path: str, force_cpu: bool = False,
                        preferred_hwaccel: str | None = None):
    """Pick encoder & output params matching input depth/chroma.
    422 is downgraded to 420 (unsupported on <RTX 50 series NVENC).

    Args:
        preferred_hwaccel: 'cuda' | 'd3d11va' | 'qsv' — prioritize the
            matching encoder family. None defaults to NVENC > AMF > QSV.
    """
    from app.core.ffmpeg import check_encoder_support, get_video_info
    codec, pix_fmt = get_video_info(video_path)
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

    # GPU path — build ordered encoder groups
    if in_chroma == '422':
        out_chroma = '420'
        downgrade_msg = f"原视频{in_chroma} GPU不支持，降为{out_chroma}"
    else:
        out_chroma = in_chroma
        downgrade_msg = ''

    has_h264_nv = check_encoder_support('h264_nvenc')
    has_hevc_nv = check_encoder_support('hevc_nvenc')
    has_h264_amf = check_encoder_support('h264_amf')
    has_hevc_amf = check_encoder_support('hevc_amf')
    has_h264_qsv = check_encoder_support('h264_qsv')
    has_hevc_qsv = check_encoder_support('hevc_qsv')

    # Each group: (hwaccel, h264_enc, hevc_enc, has_h264, has_hevc)
    _groups = [
        ('cuda',    H264_NVENC, HEVC_NVENC, has_h264_nv, has_hevc_nv),
        ('d3d11va', H264_AMF,   HEVC_AMF,   has_h264_amf, has_hevc_amf),
        ('qsv',     H264_QSV,   HEVC_QSV,   has_h264_qsv, has_hevc_qsv),
    ]

    # Reorder: move preferred group to front
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
