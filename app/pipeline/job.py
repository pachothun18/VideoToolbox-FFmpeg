import os
import shutil

from app.core.filesystem import create_temp_work_dir, create_hardlink_or_copy
from app.commands.builder import FFmpegCommandBuilder
from app.commands.profiles import EncoderProfile
from app.pipeline.executor import run_ffmpeg


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
) -> tuple[bool, list[str]]:
    work_dir = create_temp_work_dir()
    try:
        temp_video = os.path.join(work_dir, "input" + os.path.splitext(video_path)[1])
        create_hardlink_or_copy(video_path, temp_video)

        temp_sub = None
        sub_filename = None
        if sub_path:
            sub_ext = os.path.splitext(sub_path)[1]  # '.srt' or '.ass'
            sub_filename = f"sub{sub_ext}"
            temp_sub = os.path.join(work_dir, sub_filename)
            shutil.copy2(sub_path, temp_sub)

        builder = FFmpegCommandBuilder()
        builder.set_input(os.path.basename(temp_video),
                          use_hwaccel=encoder.use_gpu,
                          hwaccel_type=encoder.hwaccel)
        builder.set_gpu_index(gpu_index, hwaccel_type)

        if temp_sub:
            builder.add_video_filter(f"subtitles={sub_filename}")
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
        ok, errors = run_ffmpeg(cmd, cwd=work_dir)

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
