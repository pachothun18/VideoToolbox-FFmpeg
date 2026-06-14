import subprocess
import functools
from app.config import FFMPEG_PATH, FFPROBE_PATH


@functools.lru_cache(maxsize=1)
def _get_ffmpeg_encoders() -> str:
    """Cache ffmpeg -encoders output (called once per session)."""
    try:
        result = subprocess.run(
            [FFMPEG_PATH, '-encoders'],
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        return result.stdout
    except Exception:
        return ''


def check_encoder_support(encoder_name):
    return encoder_name in _get_ffmpeg_encoders()


def get_video_info(video_path):
    if FFPROBE_PATH:
        cmd = [
            FFPROBE_PATH, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,pix_fmt',
            '-of', 'default=noprint_wrappers=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            codec = pix_fmt = None
            for line in result.stdout.splitlines():
                if line.startswith('codec_name='):
                    codec = line.split('=')[1]
                elif line.startswith('pix_fmt='):
                    pix_fmt = line.split('=')[1]
            return codec, pix_fmt

    import re
    cmd = [FFMPEG_PATH, '-i', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    stderr = result.stderr
    match = re.search(r'Video: (?:[^,]+), ([^,]+), ([^,]+)', stderr)
    if match:
        codec_name = match.group(1).split()[0]
        pix_fmt = match.group(2).strip()
        return codec_name, pix_fmt
    return None, None
