import os
import shutil

from app.core.ffmpeg import FFmpegRunner
from app.core.filesystem import FileScanner
from app.commands.builder import FFmpegCommandBuilder
from app.commands.profiles import EncoderProfile


def _ensure_utf8_subtitle(filepath: str) -> None:
    _COMMON_ENCODINGS = ('gbk', 'gb2312', 'gb18030', 'big5', 'shift_jis', 'euc-kr', 'iso-8859-1')
    with open(filepath, 'rb') as f:
        raw = f.read()
    try:
        raw.decode('utf-8')
        return
    except UnicodeDecodeError:
        pass
    for enc in _COMMON_ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        try:
            import chardet
            result = chardet.detect(raw)
            if result.get('encoding') and result['encoding'].lower() not in ('utf-8', 'ascii'):
                text = raw.decode(result['encoding'])
            else:
                return
        except Exception:
            return
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)


class FFmpegJob:
    def __init__(self, runner: FFmpegRunner, scanner: FileScanner,
                 builder_cls=FFmpegCommandBuilder):
        self._runner = runner
        self._scanner = scanner
        self._builder_cls = builder_cls

    def execute(
        self,
        video_path: str,
        output_path: str,
        encoder: EncoderProfile,
        quality: int = 23,
        audio_codec: str = 'aac',
        audio_bitrate: str = '192k',
        sub_path: str | None = None,
        extra_vf: str | None = None,
        output_pix_fmt: str | None = None,
        profile: str | None = None,
        extra_args: str | None = None,
        gpu_index: int | None = None,
        hwaccel_type: str | None = None,
        threads: int | None = None,
    ) -> tuple[bool, list[str]]:
        work_dir = self._scanner.create_work_dir()
        try:
            temp_video = os.path.join(work_dir, "input" + os.path.splitext(video_path)[1])
            self._scanner.hardlink_or_copy(video_path, temp_video)

            temp_sub = None
            sub_filename = None
            if sub_path:
                sub_ext = os.path.splitext(sub_path)[1]
                sub_filename = f"sub{sub_ext}"
                temp_sub = os.path.join(work_dir, sub_filename)
                shutil.copy2(sub_path, temp_sub)
                _ensure_utf8_subtitle(temp_sub)

            builder = self._builder_cls()
            builder.set_input(os.path.basename(temp_video),
                              use_hwaccel=encoder.use_gpu,
                              hwaccel_type=encoder.hwaccel)
            builder.set_gpu_index(gpu_index, hwaccel_type)
            builder.set_threads(threads)

            if temp_sub:
                escaped = sub_filename.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
                builder.add_video_filter(f"subtitles={escaped}")
            if extra_vf:
                builder.add_video_filter(extra_vf)

            builder.set_video_encoder(encoder)
            enc_name = encoder.name
            builder.set_profile(profile)
            builder.set_output_pix_fmt(output_pix_fmt)
            builder.set_quality(quality, param=encoder.quality_param, rate_control=encoder.rate_control)
            builder.set_audio(audio_codec, audio_bitrate)
            if extra_args:
                builder.set_extra_args(extra_args)
            out_ext = os.path.splitext(output_path)[1] or '.mp4'
            temp_out_name = f'output_temp{out_ext}'
            builder.set_output(temp_out_name)

            cmd = builder.build()
            cmd_str = ' '.join(cmd)
            ok, errors = self._runner.run(cmd, cwd=work_dir)

            if ok:
                shutil.move(os.path.join(work_dir, temp_out_name), output_path)
                return True, [f"编码器: {enc_name}", f"命令: {cmd_str}", f"成功: {output_path}"]
            else:
                return False, [f"编码器: {enc_name}", f"命令: {cmd_str}"] + errors
        except Exception as e:
            return False, [f"异常: {e}"]
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


def run_job(
    video_path: str,
    output_path: str,
    encoder: EncoderProfile,
    quality: int,
    audio_codec: str = 'aac',
    audio_bitrate: str = '192k',
    sub_path: str | None = None,
    extra_vf: str | None = None,
    output_pix_fmt: str | None = None,
    profile: str | None = None,
    extra_args: str | None = None,
    gpu_index: int | None = None,
    hwaccel_type: str | None = None,
    threads: int | None = None,
) -> tuple[bool, list[str]]:
    from app import _runner, _scanner
    job = FFmpegJob(_runner, _scanner)
    return job.execute(
        video_path, output_path, encoder,
        quality=quality,
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate,
        sub_path=sub_path,
        extra_vf=extra_vf,
        output_pix_fmt=output_pix_fmt,
        profile=profile,
        extra_args=extra_args,
        gpu_index=gpu_index,
        hwaccel_type=hwaccel_type,
        threads=threads,
    )