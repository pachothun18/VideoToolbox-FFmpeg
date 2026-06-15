import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.ffmpeg import FFmpegRunner
from app.core.filesystem import FileScanner
from app.commands.profiles import EncoderProfile, EncoderRegistry
from app.commands.bitdepth import resolve_pixel_format, effective_chroma
from app.pipeline.job import FFmpegJob


class LogBuffer:
    def __init__(self):
        self._lines = []

    def emit(self, msg: str) -> str:
        self._lines.append(str(msg))
        return "\n".join(self._lines)

    def emit_many(self, msgs: list[str]) -> str:
        for m in msgs:
            self._lines.append(str(m))
        return "\n".join(self._lines)


def _execute_job_wrapper(job, video_path, output_path, encoder, quality,
                         audio_codec, audio_bitrate, sub_path, extra_vf,
                         output_pix_fmt, profile, extra_args, gpu_index,
                         hwaccel_type, threads):
    ok, logs = job.execute(
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
    return ok, logs


class BatchProcessor:
    def __init__(self, job: FFmpegJob, scanner: FileScanner, registry: EncoderRegistry):
        self._job = job
        self._scanner = scanner
        self._registry = registry
        self._runner = job._runner

    def from_directory(
        self,
        input_dir: str,
        output_dir: str,
        force_cpu: bool = False,
        with_subtitles: bool = False,
        crf_value: int = 23,
        audio_codec: str = 'aac',
        audio_bitrate: str = '128k',
        out_format: str = 'mp4',
        output_suffix: str = '',
        gpu_index: int | None = None,
        hwaccel_type: str | None = None,
        max_workers: int = 1,
    ):
        log = LogBuffer()
        input_dir = os.path.abspath(input_dir)
        output_dir = os.path.abspath(output_dir)

        if not os.path.exists(input_dir):
            yield log.emit("错误：输入目录不存在")
            return

        yield log.emit(f"输入目录: {input_dir}")
        yield log.emit(f"输出目录: {output_dir}")
        yield log.emit("正在扫描...")

        if with_subtitles:
            items = self._scanner.find_video_subtitle_pairs(input_dir)
            if not items:
                yield log.emit("未找到匹配的视频和字幕文件对。")
                return
            yield log.emit(f"找到 {len(items)} 个视频-字幕对。")
        else:
            raw_videos = self._scanner.find_videos(input_dir)
            items = [(v, None, d) for v, d in raw_videos]
            if not items:
                yield log.emit("未找到任何视频文件。")
                return
            yield log.emit(f"找到 {len(items)} 个视频文件。")

        suffix = output_suffix or ('_hardsub' if with_subtitles else '')
        total = len(items)
        success_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}

            for idx, (video_path, sub_path, rel_dir) in enumerate(items, 1):
                basename = os.path.basename(video_path)
                yield log.emit(f"\n[{idx}/{total}] 处理: {basename}")

                out_subdir = os.path.join(output_dir, rel_dir)
                os.makedirs(out_subdir, exist_ok=True)

                name_without_ext = os.path.splitext(basename)[0]
                output_path = os.path.join(out_subdir, f"{name_without_ext}{suffix}.{out_format}")

                if os.path.exists(output_path):
                    yield log.emit(f"  跳过: {output_path}")
                    success_count += 1
                    continue

                encoder, out_pix_fmt, profile, custom_vf, msg = self._registry.auto_select(
                    video_path, force_cpu, preferred_hwaccel=hwaccel_type)
                yield log.emit(f"  {msg}")
                yield log.emit(f"  编码器: {encoder.name}  pix_fmt: {out_pix_fmt}  profile: {profile}")

                threads = max(1, (os.cpu_count() or 4) // max_workers) if max_workers > 1 else None
                future = executor.submit(
                    _execute_job_wrapper,
                    self._job, video_path, output_path, encoder,
                    crf_value, audio_codec, audio_bitrate, sub_path,
                    custom_vf, out_pix_fmt, profile, None,
                    gpu_index, hwaccel_type, threads,
                )
                future_map[future] = idx

            for future in as_completed(future_map):
                ok, logs = future.result()
                yield log.emit_many(logs)
                if ok:
                    success_count += 1

        yield log.emit(f"\n完成！成功: {success_count}/{total}")

    def from_files(
        self,
        files: list,
        output_dir: str,
        encoder: EncoderProfile | None,
        mode: str,
        crf_value: int = 23,
        audio_codec: str = 'aac',
        audio_bitrate: str = '128k',
        out_format: str = 'mp4',
        gpu_index: int | None = None,
        hwaccel_type: str | None = None,
        max_workers: int = 1,
    ):
        log = LogBuffer()
        if not files:
            yield log.emit("未选择任何文件。")
            return

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        total = len(files)
        success_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}

            for idx, file_obj in enumerate(files, 1):
                temp_path = file_obj.name
                orig_name = file_obj.orig_name if hasattr(file_obj, 'orig_name') else os.path.basename(temp_path)
                video_basename = os.path.splitext(orig_name)[0]
                yield log.emit(f"\n[{idx}/{total}] 处理: {orig_name}")

                sub_path = None
                if mode == "subtitle":
                    base_dir = os.path.dirname(temp_path) if hasattr(file_obj, 'orig_name') else os.path.dirname(temp_path)
                    for ext in ['.ass', '.srt']:
                        candidate = os.path.join(base_dir, video_basename + ext)
                        if os.path.exists(candidate):
                            sub_path = candidate
                            yield log.emit(f"  找到字幕: {os.path.basename(candidate)}")
                            break
                    if not sub_path:
                        yield log.emit("  未找到同名字幕，跳过字幕烧录，仅转码")

                suffix = "_hardsub" if (mode == "subtitle" and sub_path) else ""
                output_filename = f"{video_basename}{suffix}.{out_format}"
                output_path = os.path.join(output_dir, output_filename)

                if os.path.exists(output_path):
                    yield log.emit(f"  跳过: {output_path}")
                    success_count += 1
                    continue

                if encoder is None:
                    enc, out_fmt, profile, custom_vf, msg = self._registry.auto_select(
                        temp_path, preferred_hwaccel=hwaccel_type)
                    yield log.emit(f"  {msg}")
                    yield log.emit(f"  编码器: {enc.name}  pix_fmt: {out_fmt}  profile: {profile}")
                else:
                    enc, out_fmt, profile, custom_vf = encoder, None, None, None

                threads = max(1, (os.cpu_count() or 4) // max_workers) if max_workers > 1 else None
                future = executor.submit(
                    _execute_job_wrapper,
                    self._job, temp_path, output_path, enc,
                    crf_value, audio_codec, audio_bitrate, sub_path,
                    custom_vf, out_fmt, profile, None,
                    gpu_index, hwaccel_type, threads,
                )
                future_map[future] = idx

            for future in as_completed(future_map):
                ok, logs = future.result()
                yield log.emit_many(logs)
                if ok:
                    success_count += 1

        yield log.emit(f"\n完成！成功: {success_count}/{total}")

    def general_convert(
        self,
        files: list,
        output_dir: str,
        out_format: str,
        encoder: EncoderProfile | None,
        target_depth: str,
        chroma: str,
        quality: int,
        audio_codec: str,
        audio_bitrate: str,
        extra_args: str | None = None,
        gpu_index: int | None = None,
        hwaccel_type: str | None = None,
        max_workers: int = 1,
    ):
        log = LogBuffer()
        if not files:
            yield log.emit("未选择任何文件。")
            return

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        total = len(files)
        success_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}

            for idx, f in enumerate(files, 1):
                temp_path = f.name
                orig_name = f.orig_name if hasattr(f, 'orig_name') else os.path.basename(temp_path)
                basename = os.path.splitext(orig_name)[0]
                out_path = os.path.join(output_dir, f"{basename}.{out_format}")

                if os.path.exists(out_path):
                    yield log.emit(f"[{idx}/{total}] 跳过（已存在）: {out_path}")
                    success_count += 1
                    continue

                yield log.emit(f"[{idx}/{total}] 转换: {orig_name} -> {out_path}")

                if encoder is None:
                    cur_enc, out_pix_fmt, profile, custom_vf, msg = self._registry.auto_select(
                        temp_path, preferred_hwaccel=hwaccel_type)
                    yield log.emit(f"  自动选择: {msg}")
                else:
                    cur_enc = encoder
                    yield log.emit(f"  编码器: {cur_enc.name}, 质量: {quality}, 位深: {target_depth}, 色度: {chroma}")
                    input_codec, input_pix_fmt = self._runner.get_video_info(temp_path)
                    yield log.emit(f"  输入: codec={input_codec}, pix_fmt={input_pix_fmt}")
                    out_pix_fmt, custom_vf, profile = resolve_pixel_format(input_pix_fmt, target_depth, chroma, cur_enc)

                    if cur_enc.use_gpu and effective_chroma(chroma, input_pix_fmt) != '420':
                        yield log.emit("  ℹ 非420色度：停用hwaccel解码，仅用GPU编码")
                        cur_enc = EncoderProfile(
                            name=cur_enc.name, label=cur_enc.label,
                            use_gpu=False, hwaccel=None,
                            default_pix_fmt=cur_enc.default_pix_fmt,
                            supports_10bit=cur_enc.supports_10bit,
                            pix_fmt_10bit=cur_enc.pix_fmt_10bit,
                            quality_param=cur_enc.quality_param,
                            rate_control=cur_enc.rate_control,
                            _profile_map=cur_enc._profile_map,
                        )
                        out_pix_fmt, custom_vf, profile = resolve_pixel_format(input_pix_fmt, target_depth, chroma, cur_enc)

                yield log.emit(f"  编码器: {cur_enc.name}  pix_fmt: {out_pix_fmt}  profile: {profile}")
                if custom_vf:
                    yield log.emit(f"  vf_filter: {custom_vf}")

                threads = max(1, (os.cpu_count() or 4) // max_workers) if max_workers > 1 else None
                future = executor.submit(
                    _execute_job_wrapper,
                    self._job, temp_path, out_path, cur_enc,
                    quality, audio_codec, audio_bitrate, None,
                    custom_vf, out_pix_fmt, profile, extra_args,
                    gpu_index, hwaccel_type, threads,
                )
                future_map[future] = idx

            for future in as_completed(future_map):
                ok, logs = future.result()
                yield log.emit_many(logs)
                if ok:
                    success_count += 1

        yield log.emit(f"\n完成！成功: {success_count}/{total}")


def run_batch_from_directory(*args, **kwargs):
    from app import _batch
    yield from _batch.from_directory(*args, **kwargs)


def run_batch_from_files(*args, **kwargs):
    from app import _batch
    yield from _batch.from_files(*args, **kwargs)


def run_general_convert(*args, **kwargs):
    from app import _batch
    yield from _batch.general_convert(*args, **kwargs)
