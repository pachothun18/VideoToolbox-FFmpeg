from app.commands.profiles import EncoderProfile

_10BIT_FMTS = {'yuv420p10le', 'yuv422p10le', 'yuv444p10le', 'p010le'}

_CHROMA_FROM_PIX = {
    'yuv420p': '420', 'yuvj420p': '420', 'p010le': '420',
    'yuv420p10le': '420', 'yuv420p12le': '420',
    'yuv422p': '422', 'yuvj422p': '422',
    'yuv422p10le': '422', 'yuv422p12le': '422',
    'yuv444p': '444', 'yuvj444p': '444',
    'yuv444p10le': '444', 'yuv444p12le': '444',
}


def is_10bit_pix_fmt(pix_fmt: str) -> bool:
    return pix_fmt in _10BIT_FMTS


def effective_chroma(chroma: str, input_pix_fmt: str | None) -> str:
    """Resolve chroma selection. 'auto' means inherit from input, defaulting to 420."""
    if chroma != 'auto':
        return chroma
    return _CHROMA_FROM_PIX.get(input_pix_fmt or '', '420')


def _infer_chroma(input_pix_fmt: str | None) -> str:
    if input_pix_fmt:
        return _CHROMA_FROM_PIX.get(input_pix_fmt, '420')
    return '420'


def resolve_pixel_format(
    input_pix_fmt: str | None,
    target_depth: str,       # 'auto' | '8bit' | '10bit'
    chroma: str,             # 'auto' | '420' | '422' | '444'
    encoder: EncoderProfile,
) -> tuple[str | None, str | None, str | None]:
    """Return (output_pix_fmt, vf_filter, profile).

    vf_filter is a format=... string for explicit pixel-format conversion.
    profile is the -profile:v value for 10bit encoding.
    """
    input_is_10bit = input_pix_fmt in _10BIT_FMTS if input_pix_fmt else False
    actual_chroma = _infer_chroma(input_pix_fmt) if chroma == 'auto' else chroma

    # Resolve target depth
    if target_depth == 'auto':
        if input_is_10bit and encoder.supports_10bit:
            depth = '10bit'
        else:
            depth = '8bit'
    else:
        depth = target_depth

    # Handle unsupported 10bit → fallback to 8bit
    if depth == '10bit' and not encoder.supports_10bit:
        depth = '8bit'

    out_fmt = encoder.get_pix_fmt(depth, actual_chroma)
    if out_fmt is None:
        out_fmt = encoder.get_pix_fmt('8bit', actual_chroma)

    # Determine if we need an explicit format filter
    vf = None
    if out_fmt and input_pix_fmt and input_pix_fmt != out_fmt:
        if encoder.use_gpu or depth != _infer_depth(input_pix_fmt):
            vf = f'format={out_fmt}'

    profile = encoder.get_profile(depth, actual_chroma)

    return out_fmt, vf, profile


def _infer_depth(pix_fmt: str | None) -> str:
    if not pix_fmt:
        return '8bit'
    return '10bit' if pix_fmt in _10BIT_FMTS else '8bit'
