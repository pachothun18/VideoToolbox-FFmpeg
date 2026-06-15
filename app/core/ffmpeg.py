"""FFmpeg 进程管理、编码器检测、视频信息查询。"""
import re
import subprocess


class FFmpegRunner:
    """封装 FFmpeg/FFprobe 命令执行，带超时保护和编码器缓存。"""

    def __init__(self, ffmpeg_path: str, ffprobe_path: str, timeout: int = 3600):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.timeout = timeout
        self._encoders_cache: str | None = None

    # ── 命令执行 ────────────────────────────────────────────────────

    def run(self, cmd: list[str], cwd: str | None = None) -> tuple[bool, list[str]]:
        """执行 FFmpeg 命令，返回 (成功, 日志行列表)。"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                cwd=cwd,
                timeout=self.timeout,
            )
            if result.returncode == 0:
                return True, []
            errors = []
            if result.stderr:
                for line in result.stderr.strip().split('\n'):
                    errors.append(f"FFmpeg错误: {line}")
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    errors.append(f"FFmpeg输出: {line}")
            return False, errors
        except subprocess.TimeoutExpired:
            return False, [f"FFmpeg 超时（>{self.timeout}s），已终止"]
        except Exception as e:
            return False, [f"异常: {str(e)}"]

    # ── 编码器检测 ──────────────────────────────────────────────────

    def _ensure_encoders_cache(self) -> str:
        """懒加载并缓存 ffmpeg -encoders 输出。"""
        if self._encoders_cache is None:
            try:
                result = subprocess.run(
                    [self.ffmpeg_path, '-encoders'],
                    capture_output=True, text=True, encoding='utf-8', errors='ignore',
                )
                self._encoders_cache = result.stdout
            except Exception:
                self._encoders_cache = ''
        return self._encoders_cache

    def check_encoder(self, name: str) -> bool:
        """检测指定编码器是否可用。"""
        return name in self._ensure_encoders_cache()

    # ── 视频信息 ────────────────────────────────────────────────────

    def get_video_info(self, video_path: str) -> tuple[str | None, str | None]:
        """获取视频编码格式和像素格式，返回 (codec_name, pix_fmt)。"""
        info = self._probe_video(video_path)
        if info is not None:
            return info
        return self._ffprobe_fallback(video_path)

    def _probe_video(self, video_path: str) -> tuple[str | None, str | None] | None:
        """用 ffprobe 查询视频流信息。"""
        if not self.ffprobe_path:
            return None
        cmd = [
            self.ffprobe_path, '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,pix_fmt',
            '-of', 'default=noprint_wrappers=1',
            video_path,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore',
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        codec = pix_fmt = None
        for line in result.stdout.splitlines():
            if line.startswith('codec_name='):
                codec = line.split('=', 1)[1]
            elif line.startswith('pix_fmt='):
                pix_fmt = line.split('=', 1)[1]
        return codec, pix_fmt

    def _ffprobe_fallback(self, video_path: str) -> tuple[str | None, str | None]:
        """ffprobe 不可用时，从 ffmpeg -i 的 stderr 解析信息。"""
        cmd = [self.ffmpeg_path, '-i', video_path]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore',
            )
        except Exception:
            return None, None
        match = re.search(r'Video: (?:[^,]+), ([^,]+), ([^,]+)', result.stderr)
        if match:
            codec_name = match.group(1).split()[0]
            pix_fmt = match.group(2).strip()
            return codec_name, pix_fmt
        return None, None


# ── 向后兼容的独立函数 ────────────────────────────────────────────

_LEGACY_RUNNER: 'FFmpegRunner | None' = None


def _get_legacy_runner() -> 'FFmpegRunner':
    global _LEGACY_RUNNER
    if _LEGACY_RUNNER is None:
        from app.config import FFMPEG_PATH, FFPROBE_PATH
        _LEGACY_RUNNER = FFmpegRunner(FFMPEG_PATH, FFPROBE_PATH)
    return _LEGACY_RUNNER


def check_encoder_support(name: str) -> bool:
    return _get_legacy_runner().check_encoder(name)


def get_video_info(video_path: str) -> tuple[str | None, str | None]:
    return _get_legacy_runner().get_video_info(video_path)
