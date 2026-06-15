from app.config import FFMPEG_PATH, FFPROBE_PATH, IGNORE_DIRS, VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS, PREFERRED_LANG
from app.core.ffmpeg import FFmpegRunner
from app.core.filesystem import FileScanner
from app.core.gpu import GPUDetector
from app.commands.profiles import EncoderRegistry
from app.pipeline.job import FFmpegJob
from app.pipeline.batch import BatchProcessor

_runner = FFmpegRunner(FFMPEG_PATH, FFPROBE_PATH)
_scanner = FileScanner(IGNORE_DIRS, VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS, PREFERRED_LANG)
_detector = GPUDetector(_runner)
_registry = EncoderRegistry(_runner)
_job = FFmpegJob(_runner, _scanner)
_batch = BatchProcessor(_job, _scanner, _registry)
_gpus = _detector.detect_all()