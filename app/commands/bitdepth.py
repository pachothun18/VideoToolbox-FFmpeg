from app.commands.profiles import EncoderProfile


class PixelFormatResolver:
    _10BIT_FMTS = frozenset({'yuv420p10le', 'yuv422p10le', 'yuv444p10le', 'p010le', 'p010'})

    _CHROMA_MAP = {
        'yuv420p': '420', 'yuvj420p': '420', 'nv12': '420',
        'p010le': '420', 'p010': '420',
        'yuv420p10le': '420', 'yuv420p12le': '420',
        'yuv422p': '422', 'yuvj422p': '422',
        'yuv422p10le': '422', 'yuv422p12le': '422',
        'yuv444p': '444', 'yuvj444p': '444',
        'yuv444p10le': '444', 'yuv444p12le': '444',
    }

    @staticmethod
    def is_10bit(pix_fmt: str) -> bool:
        return pix_fmt in PixelFormatResolver._10BIT_FMTS

    @staticmethod
    def infer_chroma(pix_fmt: str | None) -> str:
        if pix_fmt:
            return PixelFormatResolver._CHROMA_MAP.get(pix_fmt, '420')
        return '420'

    @staticmethod
    def resolve(input_pix_fmt, target_depth, chroma, encoder) -> tuple:
        input_is_10bit = input_pix_fmt in PixelFormatResolver._10BIT_FMTS if input_pix_fmt else False
        actual_chroma = PixelFormatResolver.infer_chroma(input_pix_fmt) if chroma == 'auto' else chroma

        if target_depth == 'auto':
            if input_is_10bit and encoder.supports_10bit:
                depth = '10bit'
            else:
                depth = '8bit'
        else:
            depth = target_depth

        if depth == '10bit' and not encoder.supports_10bit:
            depth = '8bit'

        out_fmt = encoder.get_pix_fmt(depth, actual_chroma)
        if out_fmt is None:
            out_fmt = encoder.get_pix_fmt('8bit', actual_chroma)

        vf = None
        if out_fmt and input_pix_fmt and input_pix_fmt != out_fmt:
            if encoder.use_gpu or depth != PixelFormatResolver._infer_depth(input_pix_fmt):
                vf = f'format={out_fmt}'

        profile = encoder.get_profile(depth, actual_chroma)

        return out_fmt, vf, profile

    @staticmethod
    def _infer_depth(pix_fmt: str | None) -> str:
        if not pix_fmt:
            return '8bit'
        return '10bit' if pix_fmt in PixelFormatResolver._10BIT_FMTS else '8bit'


def is_10bit_pix_fmt(pix_fmt: str) -> bool:
    return PixelFormatResolver.is_10bit(pix_fmt)


def effective_chroma(chroma: str, input_pix_fmt: str | None) -> str:
    if chroma != 'auto':
        return chroma
    return PixelFormatResolver._CHROMA_MAP.get(input_pix_fmt or '', '420')


def _infer_chroma(input_pix_fmt: str | None) -> str:
    return PixelFormatResolver.infer_chroma(input_pix_fmt)


def resolve_pixel_format(
    input_pix_fmt: str | None,
    target_depth: str,
    chroma: str,
    encoder: EncoderProfile,
) -> tuple[str | None, str | None, str | None]:
    return PixelFormatResolver.resolve(input_pix_fmt, target_depth, chroma, encoder)


def _infer_depth(pix_fmt: str | None) -> str:
    return PixelFormatResolver._infer_depth(pix_fmt)


def _parse_pix_fmt(pix_fmt: str | None) -> tuple[str, str]:
    if not pix_fmt:
        return '8bit', '420'
    if pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le',
                   'p010le', 'p010', 'p016le'):
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