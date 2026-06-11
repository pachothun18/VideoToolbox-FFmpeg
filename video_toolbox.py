#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理工具箱 - Gradio WebUI
功能：GPU/CPU字幕烧录、GPU/CPU视频转码、批量上传、通用视频转换
新增：输出位深手动选择（8bit/10bit/自动），移除进度条
"""

import os
import sys
import re
import shutil
import subprocess
import tempfile
import random
import string
import threading
import webbrowser
import socket
from pathlib import Path

import gradio as gr

# ========== 路径处理 ==========
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

BASE_DIR = get_base_dir()

# ========== FFmpeg 检测 ==========
FFMPEG_PATH = shutil.which("ffmpeg")
FFPROBE_PATH = shutil.which("ffprobe")

local_ffmpeg = BASE_DIR / "ffmpeg.exe"
local_ffprobe = BASE_DIR / "ffprobe.exe"
if local_ffmpeg.exists():
    FFMPEG_PATH = str(local_ffmpeg)
if local_ffprobe.exists():
    FFPROBE_PATH = str(local_ffprobe)

if not FFMPEG_PATH:
    FFMPEG_PATH = "ffmpeg"
if not FFPROBE_PATH:
    FFPROBE_PATH = "ffprobe"

# ========== 全局配置 ==========
IGNORE_DIRS = {'output', 'fonts', 'python', '__pycache__', '.git'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.rmvb'}
SUBTITLE_EXTENSIONS = {'.ass', '.srt'}
PREFERRED_LANG = 'SC'

# ========== 辅助函数 ==========
def random_str(k=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=k))

def check_encoder_support(encoder_name):
    try:
        cmd = [FFMPEG_PATH, '-encoders']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        return encoder_name in result.stdout
    except:
        return False

def get_nvidia_gpu_info():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'],
                                capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()
    except:
        pass
    return None, None

def get_video_info(video_path):
    if os.path.exists(FFPROBE_PATH):
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
    cmd = [FFMPEG_PATH, '-i', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    stderr = result.stderr
    match = re.search(r'Video: (?:[^,]+), ([^,]+), ([^,]+)', stderr)
    if match:
        codec_name = match.group(1).split()[0]
        pix_fmt = match.group(2).strip()
        return codec_name, pix_fmt
    return None, None

def create_temp_work_dir():
    temp_base = tempfile.gettempdir()
    job_id = random_str(8)
    work_dir = os.path.join(temp_base, f'ffmpeg_job_{job_id}')
    os.makedirs(work_dir, exist_ok=True)
    return work_dir

def create_hardlink_or_copy(src, dst):
    try:
        os.link(src, dst)
        return 'link'
    except:
        shutil.copy2(src, dst)
        return 'copy'

def find_all_video_subtitle_pairs(root_dir):
    pairs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        videos, subs = [], []
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                videos.append(f)
            elif ext in SUBTITLE_EXTENSIONS:
                subs.append(f)
        for v in videos:
            v_name = os.path.splitext(v)[0]
            candidates = [s for s in subs if s.lower().startswith(v_name.lower())]
            if not candidates:
                continue
            if PREFERRED_LANG:
                lang_candidates = [s for s in candidates if f'.{PREFERRED_LANG}-' in s or f'.{PREFERRED_LANG}.' in s]
                if lang_candidates:
                    candidates = lang_candidates
            chosen = next((s for s in candidates if s.lower().endswith('.ass')), candidates[0])
            video_path = os.path.join(dirpath, v)
            sub_path = os.path.join(dirpath, chosen)
            rel_dir = os.path.relpath(dirpath, root_dir)
            if rel_dir == '.':
                rel_dir = ''
            pairs.append((video_path, sub_path, rel_dir))
    return pairs

def find_all_videos(root_dir):
    videos = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                full_path = os.path.join(dirpath, f)
                rel_dir = os.path.relpath(dirpath, root_dir)
                if rel_dir == '.':
                    rel_dir = ''
                videos.append((full_path, rel_dir))
    return videos

# ========== 核心转码函数（支持色深控制） ==========
def run_ffmpeg(cmd, log_prefix=""):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            return True, []
        else:
            errors = []
            if result.stderr:
                errors.extend([f"{log_prefix}FFmpeg错误: {line}" for line in result.stderr.strip().split('\n')])
            if result.stdout:
                errors.extend([f"{log_prefix}FFmpeg输出: {line}" for line in result.stdout.strip().split('\n')])
            return False, errors
    except Exception as e:
        return False, [f"{log_prefix}异常: {str(e)}"]

def transcode_single_video(video_path, output_path, crf_value, audio_bitrate, use_gpu, encoder, output_pix_fmt=None, profile=None, extra_args=None, custom_vf=None):
    work_dir = create_temp_work_dir()
    try:
        temp_video = os.path.join(work_dir, "input" + os.path.splitext(video_path)[1])
        create_hardlink_or_copy(video_path, temp_video)

        original_cwd = os.getcwd()
        os.chdir(work_dir)

        cmd = []
        if use_gpu:
            cmd.extend([FFMPEG_PATH, '-hwaccel', 'cuda', '-i', os.path.basename(temp_video)])
        else:
            cmd.extend([FFMPEG_PATH, '-i', os.path.basename(temp_video)])

        vf_parts = []
        if custom_vf:
            vf_parts.append(custom_vf)
        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend(['-c:v', encoder])
        if profile:
            cmd.extend(['-profile:v', profile])
        if output_pix_fmt:
            cmd.extend(['-pix_fmt', output_pix_fmt])

        if encoder in ('libx264', 'libx265'):
            cmd.extend(['-crf', str(crf_value)])
        elif encoder in ('h264_nvenc', 'hevc_nvenc'):
            cmd.extend(['-rc', 'vbr', '-cq', str(crf_value)])

        audio_codec = audio_bitrate.split()[0] if ' ' in audio_bitrate else 'aac'
        bitrate_val = audio_bitrate if 'k' in audio_bitrate else '192k'
        cmd.extend(['-c:a', audio_codec, '-b:a', bitrate_val])

        if extra_args:
            cmd.extend(extra_args.split())
        cmd.extend(['-movflags', '+faststart', '-y', 'output_temp.mp4'])

        ok, logs = run_ffmpeg(cmd, "")
        os.chdir(original_cwd)

        if ok:
            shutil.move(os.path.join(work_dir, 'output_temp.mp4'), output_path)
            return True, [f"✅ 成功: {output_path}"]
        else:
            return False, logs
    except Exception as e:
        return False, [f"⚠️ 异常: {e}"]
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except:
            pass

def process_single_video_with_subtitle(video_path, sub_path, output_path, crf_value, audio_bitrate, use_gpu, encoder, output_pix_fmt=None, profile=None, custom_vf=None):
    work_dir = create_temp_work_dir()
    try:
        temp_video = os.path.join(work_dir, "input" + os.path.splitext(video_path)[1])
        temp_sub = os.path.join(work_dir, "sub.ass")
        create_hardlink_or_copy(video_path, temp_video)
        shutil.copy2(sub_path, temp_sub)

        original_cwd = os.getcwd()
        os.chdir(work_dir)

        cmd = []
        if use_gpu:
            cmd.extend([FFMPEG_PATH, '-hwaccel', 'cuda', '-i', os.path.basename(temp_video)])
        else:
            cmd.extend([FFMPEG_PATH, '-i', os.path.basename(temp_video)])

        vf_parts = ["subtitles=sub.ass"]
        if custom_vf:
            vf_parts.append(custom_vf)
        cmd.extend(['-vf', ','.join(vf_parts)])

        cmd.extend(['-c:v', encoder])
        if profile:
            cmd.extend(['-profile:v', profile])
        if output_pix_fmt:
            cmd.extend(['-pix_fmt', output_pix_fmt])

        if encoder in ('libx264', 'libx265'):
            cmd.extend(['-crf', str(crf_value)])
        elif encoder in ('h264_nvenc', 'hevc_nvenc'):
            cmd.extend(['-rc', 'vbr', '-cq', str(crf_value)])

        cmd.extend(['-c:a', 'aac', '-b:a', audio_bitrate, '-y', 'output_temp.mp4'])

        ok, logs = run_ffmpeg(cmd, "")
        os.chdir(original_cwd)

        if ok:
            shutil.move(os.path.join(work_dir, 'output_temp.mp4'), output_path)
            return True, [f"✅ 成功: {output_path}"]
        else:
            return False, logs
    except Exception as e:
        return False, [f"⚠️ 异常: {e}"]
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except:
            pass

# ========== 智能编码器选择（用于目录模式，自动） ==========
def auto_select_encoder(video_path, force_cpu=False):
    codec, pix_fmt = get_video_info(video_path)
    is_10bit = pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le')
    has_h264_nvenc = check_encoder_support('h264_nvenc')
    has_hevc_nvenc = check_encoder_support('hevc_nvenc')

    if force_cpu:
        return 'libx264', False, 'yuv420p', None, None, "CPU (libx264, 8bit)"

    if is_10bit:
        if has_hevc_nvenc:
            return 'hevc_nvenc', True, 'p010le', 'main10', None, "GPU (HEVC 10bit保留色深)"
        else:
            # 降级到CPU 8bit（目录模式保持简单）
            return 'libx264', False, 'yuv420p', None, None, "GPU不支持10bit编码，回退CPU libx264 8bit"
    else:
        if has_h264_nvenc:
            return 'h264_nvenc', True, 'yuv420p', None, None, "GPU (H.264 8bit)"
        elif has_hevc_nvenc:
            return 'hevc_nvenc', True, 'yuv420p', None, None, "GPU (HEVC 8bit)"
        else:
            return 'libx264', False, 'yuv420p', None, None, "回退 CPU libx264 8bit"

def process_video_with_auto(video_path, sub_path, output_path, crf_value, audio_bitrate, force_cpu=False):
    encoder, use_gpu, out_pix_fmt, profile, custom_vf, msg = auto_select_encoder(video_path, force_cpu)
    logs = [f"📊 {msg}"]
    if sub_path:
        ok, res = process_single_video_with_subtitle(video_path, sub_path, output_path, crf_value, audio_bitrate,
                                                     use_gpu, encoder, out_pix_fmt, profile, custom_vf)
    else:
        ok, res = transcode_single_video(video_path, output_path, crf_value, audio_bitrate,
                                         use_gpu, encoder, out_pix_fmt, profile, custom_vf=custom_vf)
    logs.extend(res)
    return ok, logs

# ========== 四大功能生成器（保持原样，调用 process_video_with_auto） ==========
def process_gpu_subtitle(input_dir, output_dir, crf_value=23, audio_bitrate='128k'):
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    if not os.path.exists(input_dir):
        yield "错误：输入目录不存在"
        return
    yield f"📁 输入目录: {input_dir}"
    yield f"📁 输出目录: {output_dir}"
    yield "🔍 正在扫描视频-字幕对..."
    pairs = find_all_video_subtitle_pairs(input_dir)
    if not pairs:
        yield "未找到匹配的视频和字幕文件对。"
        return
    yield f"找到 {len(pairs)} 个任务。\n"
    success = 0
    for idx, (video_path, sub_path, rel_dir) in enumerate(pairs, 1):
        yield f"\n[{idx}/{len(pairs)}] 处理: {os.path.basename(video_path)}"
        out_subdir = os.path.join(output_dir, rel_dir)
        os.makedirs(out_subdir, exist_ok=True)
        name_without_ext = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(out_subdir, f"{name_without_ext}_hardsub.mp4")
        if os.path.exists(output_path):
            yield f"  ⏭️ 跳过: {output_path}"
            success += 1
            continue
        ok, logs = process_video_with_auto(video_path, sub_path, output_path, crf_value, audio_bitrate, force_cpu=False)
        for log in logs:
            yield log
        if ok:
            success += 1
    yield f"\n🎉 完成！成功: {success}/{len(pairs)}"

def process_cpu_subtitle(input_dir, output_dir, crf_value=23, audio_bitrate='128k'):
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    if not os.path.exists(input_dir):
        yield "错误：输入目录不存在"
        return
    yield f"📁 输入目录: {input_dir}"
    yield f"📁 输出目录: {output_dir}"
    yield "🔍 正在扫描视频-字幕对..."
    pairs = find_all_video_subtitle_pairs(input_dir)
    if not pairs:
        yield "未找到匹配的视频和字幕文件对。"
        return
    yield f"找到 {len(pairs)} 个任务。\n"
    success = 0
    for idx, (video_path, sub_path, rel_dir) in enumerate(pairs, 1):
        yield f"\n[{idx}/{len(pairs)}] 处理: {os.path.basename(video_path)}"
        out_subdir = os.path.join(output_dir, rel_dir)
        os.makedirs(out_subdir, exist_ok=True)
        name_without_ext = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(out_subdir, f"{name_without_ext}_hardsub.mp4")
        if os.path.exists(output_path):
            yield f"  ⏭️ 跳过: {output_path}"
            success += 1
            continue
        ok, logs = process_video_with_auto(video_path, sub_path, output_path, crf_value, audio_bitrate, force_cpu=True)
        for log in logs:
            yield log
        if ok:
            success += 1
    yield f"\n🎉 完成！成功: {success}/{len(pairs)}"

def process_gpu_transcode(input_dir, output_dir, crf_value=23, audio_bitrate='192k'):
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    if not os.path.exists(input_dir):
        yield "错误：输入目录不存在"
        return
    yield f"📁 输入目录: {input_dir}"
    yield f"📁 输出目录: {output_dir}"
    yield "🔍 正在扫描视频文件..."
    videos = find_all_videos(input_dir)
    if not videos:
        yield "未找到任何视频文件。"
        return
    yield f"找到 {len(videos)} 个视频文件。\n"
    success = 0
    for idx, (video_path, rel_dir) in enumerate(videos, 1):
        yield f"\n[{idx}/{len(videos)}] 处理: {os.path.basename(video_path)}"
        out_subdir = os.path.join(output_dir, rel_dir)
        os.makedirs(out_subdir, exist_ok=True)
        name_without_ext = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(out_subdir, f"{name_without_ext}.mp4")
        if os.path.exists(output_path):
            yield f"  ⏭️ 跳过: {output_path}"
            success += 1
            continue
        ok, logs = process_video_with_auto(video_path, None, output_path, crf_value, audio_bitrate, force_cpu=False)
        for log in logs:
            yield log
        if ok:
            success += 1
    yield f"\n🎉 完成！成功: {success}/{len(videos)}"

def process_cpu_transcode(input_dir, output_dir, crf_value=23, audio_bitrate='192k'):
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    if not os.path.exists(input_dir):
        yield "错误：输入目录不存在"
        return
    yield f"📁 输入目录: {input_dir}"
    yield f"📁 输出目录: {output_dir}"
    yield "🔍 正在扫描视频文件..."
    videos = find_all_videos(input_dir)
    if not videos:
        yield "未找到任何视频文件。"
        return
    yield f"找到 {len(videos)} 个视频文件。\n"
    success = 0
    for idx, (video_path, rel_dir) in enumerate(videos, 1):
        yield f"\n[{idx}/{len(videos)}] 处理: {os.path.basename(video_path)}"
        out_subdir = os.path.join(output_dir, rel_dir)
        os.makedirs(out_subdir, exist_ok=True)
        name_without_ext = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(out_subdir, f"{name_without_ext}.mp4")
        if os.path.exists(output_path):
            yield f"  ⏭️ 跳过: {output_path}"
            success += 1
            continue
        ok, logs = process_video_with_auto(video_path, None, output_path, crf_value, audio_bitrate, force_cpu=True)
        for log in logs:
            yield log
        if ok:
            success += 1
    yield f"\n🎉 完成！成功: {success}/{len(videos)}"

# ========== 批量上传处理 ==========
def process_uploaded_files(files, output_dir, mode, crf_value=23, audio_bitrate='128k'):
    if not files:
        yield "未选择任何文件。"
        return
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    total = len(files)
    success_count = 0
    for idx, file_obj in enumerate(files, 1):
        temp_path = file_obj.name
        orig_name = file_obj.orig_name if hasattr(file_obj, 'orig_name') else os.path.basename(temp_path)
        video_basename = os.path.splitext(orig_name)[0]
        yield f"\n[{idx}/{total}] 处理: {orig_name}"
        sub_path = None
        if mode == "subtitle":
            base_dir = os.path.dirname(temp_path)
            for ext in ['.ass', '.srt']:
                candidate = os.path.join(base_dir, video_basename + ext)
                if os.path.exists(candidate):
                    sub_path = candidate
                    yield f"  找到字幕: {os.path.basename(candidate)}"
                    break
            if not sub_path:
                yield f"  ⚠️ 未找到同名字幕，跳过字幕烧录，仅转码"
        output_filename = f"{video_basename}_hardsub.mp4" if mode == "subtitle" else f"{video_basename}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        if os.path.exists(output_path):
            yield f"  ⏭️ 跳过: {output_path}"
            success_count += 1
            continue
        if mode == "subtitle" and sub_path:
            ok, logs = process_video_with_auto(temp_path, sub_path, output_path, crf_value, audio_bitrate, force_cpu=False)
        else:
            ok, logs = process_video_with_auto(temp_path, None, output_path, crf_value, audio_bitrate, force_cpu=False)
        for log in logs:
            yield log
        if ok:
            success_count += 1
    yield f"\n🎉 完成！成功: {success_count}/{total}"

# ========== 通用视频转换（带位深选项，无进度条） ==========
def convert_files_general(files, output_dir, fmt, enc_mode, enc_choice, bit_depth, quality_val, a_codec, a_bitrate, extra_args):
    if not files:
        yield "未选择任何文件。"
        return
    encoder_name = enc_choice
    use_gpu = (enc_mode == "GPU (NVENC)")
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    total = len(files)
    success = 0

    for idx, f in enumerate(files, 1):
        temp_path = f.name
        orig_name = f.orig_name if hasattr(f, 'orig_name') else os.path.basename(temp_path)
        basename = os.path.splitext(orig_name)[0]
        out_path = os.path.join(output_dir, f"{basename}.{fmt}")

        if os.path.exists(out_path):
            yield f"[{idx}/{total}] 跳过（已存在）: {out_path}"
            success += 1
            continue

        yield f"[{idx}/{total}] 转换: {orig_name} -> {out_path}"
        yield f"  编码模式: {enc_mode}, 编码器: {encoder_name}, 质量: {quality_val}, 输出位深: {bit_depth}"

        # 获取输入视频信息
        codec, pix_fmt = get_video_info(temp_path)
        is_input_10bit = pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le')
        output_pix_fmt = None
        custom_vf = None
        profile = None

        # 根据用户选择的位深决定输出像素格式和滤镜
        if bit_depth == "8bit":
            target_pix = "yuv420p"
            if is_input_10bit and use_gpu and encoder_name == 'h264_nvenc':
                custom_vf = "format=yuv420p"
            output_pix_fmt = target_pix
            if encoder_name in ('hevc_nvenc', 'libx265') and not use_gpu:
                # 对于HEVC编码，8bit通常不需要特殊profile
                pass
        elif bit_depth == "10bit":
            if not use_gpu:
                yield "  ⚠️ CPU模式暂不支持10bit输出，将输出8bit"
                target_pix = "yuv420p"
                output_pix_fmt = target_pix
                if is_input_10bit and encoder_name == 'h264_nvenc':
                    custom_vf = "format=yuv420p"
            else:
                if encoder_name == 'hevc_nvenc':
                    output_pix_fmt = "p010le"
                    profile = "main10"
                    if is_input_10bit:
                        # 保持10bit，无需滤镜
                        pass
                    else:
                        # 输入是8bit，输出10bit需要上采样？FFmpeg 默认不会自动升位，需要添加滤镜
                        custom_vf = "format=yuv420p10le"
                elif encoder_name == 'h264_nvenc':
                    yield "  ⚠️ H.264 NVENC不支持10bit编码，将输出8bit"
                    output_pix_fmt = "yuv420p"
                    if is_input_10bit:
                        custom_vf = "format=yuv420p"
                else:
                    yield "  ⚠️ 当前编码器不支持10bit，将输出8bit"
                    output_pix_fmt = "yuv420p"
                    if is_input_10bit:
                        custom_vf = "format=yuv420p"
        else:  # 自动
            if is_input_10bit:
                if use_gpu and encoder_name == 'hevc_nvenc' and check_encoder_support('hevc_nvenc'):
                    output_pix_fmt = "p010le"
                    profile = "main10"
                    yield "  ℹ️ 自动模式：输入10bit，使用HEVC NVENC保留10bit"
                elif use_gpu and encoder_name == 'h264_nvenc':
                    output_pix_fmt = "yuv420p"
                    custom_vf = "format=yuv420p"
                    yield "  ℹ️ 自动模式：输入10bit但使用h264_nvenc，转为8bit"
                else:
                    output_pix_fmt = "yuv420p"
                    if encoder_name in ('libx264', 'h264_nvenc'):
                        custom_vf = "format=yuv420p"
                    yield "  ℹ️ 自动模式：输入10bit，输出8bit"
            else:
                output_pix_fmt = "yuv420p"
                yield "  ℹ️ 自动模式：输入8bit，输出8bit"

        work_dir = create_temp_work_dir()
        try:
            temp_video = os.path.join(work_dir, "input" + os.path.splitext(temp_path)[1])
            create_hardlink_or_copy(temp_path, temp_video)

            original_cwd = os.getcwd()
            os.chdir(work_dir)

            cmd = []
            if use_gpu:
                cmd.extend([FFMPEG_PATH, '-hwaccel', 'cuda', '-i', os.path.basename(temp_video)])
            else:
                cmd.extend([FFMPEG_PATH, '-i', os.path.basename(temp_video)])

            if custom_vf:
                cmd.extend(['-vf', custom_vf])
            cmd.extend(['-c:v', encoder_name])
            if profile:
                cmd.extend(['-profile:v', profile])
            if output_pix_fmt:
                cmd.extend(['-pix_fmt', output_pix_fmt])

            if quality_val is not None:
                if 'nvenc' in encoder_name:
                    cmd.extend(['-rc', 'vbr', '-cq', str(quality_val)])
                else:
                    cmd.extend(['-crf', str(quality_val)])

            cmd.extend(['-c:a', a_codec])
            if a_codec != 'copy':
                cmd.extend(['-b:a', a_bitrate])

            if extra_args:
                cmd.extend(extra_args.split())
            cmd.extend(['-movflags', '+faststart', '-y', 'output_temp.mp4'])

            yield f"  执行转码中，请稍候..."

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            os.chdir(original_cwd)

            if result.returncode == 0:
                shutil.move(os.path.join(work_dir, 'output_temp.mp4'), out_path)
                yield f"  ✅ 成功: {out_path}"
                success += 1
            else:
                yield f"  ❌ 失败: {orig_name}"
                if result.stderr:
                    yield "  错误详情:"
                    for line in result.stderr.strip().split('\n')[-10:]:
                        yield f"      {line}"
                if result.stdout:
                    yield "  标准输出:"
                    for line in result.stdout.strip().split('\n')[-5:]:
                        yield f"      {line}"
        except Exception as e:
            yield f"  ⚠️ 异常: {e}"
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except:
                pass

    yield f"\n🎉 完成！成功: {success}/{total}"

# ========== Gradio 界面 ==========
def create_ui():
    with gr.Blocks() as demo:
        gr.Markdown("# 🎬 视频处理工具箱")
        gr.Markdown("支持GPU/CPU字幕烧录、GPU/CPU视频转码。递归处理子目录，保持原有结构。")

        with gr.Row():
            gpu_name, driver = get_nvidia_gpu_info()
            gpu_status = f"🖥️ GPU: {gpu_name} (驱动 {driver})" if gpu_name else "⚠️ 未检测到NVIDIA GPU"
            enc_h264 = check_encoder_support('h264_nvenc')
            enc_hevc = check_encoder_support('hevc_nvenc')
            enc_status = f"🔧 h264_nvenc: {'✅' if enc_h264 else '❌'} | hevc_nvenc: {'✅' if enc_hevc else '❌'}"
            gr.Markdown(f"**系统状态**：{gpu_status} &nbsp;&nbsp; {enc_status}")

        with gr.Tabs():
            # Tab1: GPU字幕烧录
            with gr.TabItem("🚀 GPU字幕烧录"):
                with gr.Row():
                    input_dir1 = gr.Textbox(label="输入目录", value=str(BASE_DIR), placeholder="包含视频和字幕的根目录")
                    output_dir1 = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_gpu_sub"), placeholder="输出目录")
                with gr.Row():
                    crf1 = gr.Slider(label="CRF/CQ (质量，越小越好)", minimum=18, maximum=30, step=1, value=23)
                    audio_bitrate1 = gr.Dropdown(label="音频比特率", choices=["96k", "128k", "192k", "256k"], value="128k")
                btn1 = gr.Button("开始处理", variant="primary")
                log1 = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
                btn1.click(fn=process_gpu_subtitle, inputs=[input_dir1, output_dir1, crf1, audio_bitrate1], outputs=log1)

            # Tab2: CPU字幕烧录
            with gr.TabItem("💻 CPU字幕烧录"):
                with gr.Row():
                    input_dir2 = gr.Textbox(label="输入目录", value=str(BASE_DIR), placeholder="包含视频和字幕的根目录")
                    output_dir2 = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_cpu_sub"), placeholder="输出目录")
                with gr.Row():
                    crf2 = gr.Slider(label="CRF (质量)", minimum=18, maximum=30, step=1, value=23)
                    audio_bitrate2 = gr.Dropdown(label="音频比特率", choices=["96k", "128k", "192k", "256k"], value="128k")
                btn2 = gr.Button("开始处理", variant="primary")
                log2 = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
                btn2.click(fn=process_cpu_subtitle, inputs=[input_dir2, output_dir2, crf2, audio_bitrate2], outputs=log2)

            # Tab3: GPU转码
            with gr.TabItem("⚡ GPU视频转码"):
                with gr.Row():
                    input_dir3 = gr.Textbox(label="输入目录", value=str(BASE_DIR), placeholder="包含视频的根目录")
                    output_dir3 = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_gpu_trans"), placeholder="输出目录")
                with gr.Row():
                    crf3 = gr.Slider(label="CQ (质量)", minimum=18, maximum=30, step=1, value=23)
                    audio_bitrate3 = gr.Dropdown(label="音频比特率", choices=["96k", "128k", "192k", "256k"], value="192k")
                btn3 = gr.Button("开始处理", variant="primary")
                log3 = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
                btn3.click(fn=process_gpu_transcode, inputs=[input_dir3, output_dir3, crf3, audio_bitrate3], outputs=log3)

            # Tab4: CPU转码
            with gr.TabItem("🐌 CPU视频转码"):
                with gr.Row():
                    input_dir4 = gr.Textbox(label="输入目录", value=str(BASE_DIR), placeholder="包含视频的根目录")
                    output_dir4 = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_cpu_trans"), placeholder="输出目录")
                with gr.Row():
                    crf4 = gr.Slider(label="CRF (质量)", minimum=18, maximum=30, step=1, value=23)
                    audio_bitrate4 = gr.Dropdown(label="音频比特率", choices=["96k", "128k", "192k", "256k"], value="192k")
                btn4 = gr.Button("开始处理", variant="primary")
                log4 = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
                btn4.click(fn=process_cpu_transcode, inputs=[input_dir4, output_dir4, crf4, audio_bitrate4], outputs=log4)

            # Tab5: 批量上传文件
            with gr.TabItem("📂 批量上传文件"):
                gr.Markdown("拖拽或点击添加多个视频文件（支持.mp4, .mkv, .avi等）。程序会自动查找同名字幕（仅当文件在同一目录时），并输出到指定目录。")
                with gr.Row():
                    files_input = gr.File(label="拖拽或点击添加视频文件", file_count="multiple", file_types=list(VIDEO_EXTENSIONS))
                    output_dir_upload = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_upload"), placeholder="输出目录")
                with gr.Row():
                    mode_radio = gr.Radio(label="处理模式", choices=["转码（无字幕）", "字幕烧录（需同名字幕）"], value="转码（无字幕）")
                    crf_upload = gr.Slider(label="CRF/CQ (质量)", minimum=18, maximum=30, step=1, value=23)
                    audio_bitrate_upload = gr.Dropdown(label="音频比特率", choices=["96k", "128k", "192k", "256k"], value="128k")
                log_upload = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
                btn_upload = gr.Button("开始处理", variant="primary")
                def upload_wrapper(files, output_dir, mode, crf, bitrate):
                    mode_key = "subtitle" if mode == "字幕烧录（需同名字幕）" else "transcode"
                    yield from process_uploaded_files(files, output_dir, mode_key, crf, bitrate)
                btn_upload.click(fn=upload_wrapper, inputs=[files_input, output_dir_upload, mode_radio, crf_upload, audio_bitrate_upload], outputs=log_upload)

            # Tab6: 通用视频转换（带位深选择，无进度条）
            with gr.TabItem("🔄 通用视频转换"):
                gr.Markdown("拖拽或点击添加视频文件，可选择输出格式、编码器、质量参数、输出位深等。支持GPU/CPU加速。")
                with gr.Row():
                    files_convert = gr.File(label="选择视频文件（支持批量）", file_count="multiple", file_types=None)
                    output_dir_convert = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_convert"), placeholder="输出目录")
                with gr.Row():
                    output_format = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
                    encoder_mode = gr.Radio(label="编码模式", choices=["GPU (NVENC)", "CPU"], value="GPU (NVENC)")
                with gr.Row():
                    init_choices = []
                    if check_encoder_support('h264_nvenc'):
                        init_choices.append(("h264_nvenc", "h264_nvenc (H.264)"))
                    if check_encoder_support('hevc_nvenc'):
                        init_choices.append(("hevc_nvenc", "hevc_nvenc (H.265)"))
                    if not init_choices:
                        init_choices = [
                            ("libx264", "libx264 (H.264)"),
                            ("libx265", "libx265 (H.265)"),
                            ("libsvtav1", "libsvtav1 (AV1)"),
                            ("libvpx-vp9", "libvpx-vp9 (VP9)")
                        ]
                    video_encoder = gr.Dropdown(
                        label="视频编码器",
                        choices=init_choices,
                        value=init_choices[0][0],
                        interactive=True,
                        allow_custom_value=True
                    )
                    bit_depth = gr.Dropdown(
                        label="输出位深",
                        choices=["自动（保留原色深）", "8bit", "10bit"],
                        value="自动（保留原色深）"
                    )
                    quality = gr.Slider(label="质量 (CRF/CQ)", minimum=18, maximum=35, step=1, value=23)
                with gr.Row():
                    audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
                    audio_bitrate = gr.Dropdown(label="音频比特率", choices=["96k", "128k", "192k", "256k", "320k"], value="192k")
                with gr.Row():
                    additional_params = gr.Textbox(label="额外FFmpeg参数（可选）", placeholder="例如: -preset fast -tune film")
                btn_convert = gr.Button("开始转换", variant="primary")
                log_convert = gr.Textbox(label="转换日志", lines=20, autoscroll=True)

                # 更新编码器列表
                def update_encoders(mode):
                    if mode == "GPU (NVENC)":
                        available = []
                        if check_encoder_support('h264_nvenc'):
                            available.append(("h264_nvenc", "h264_nvenc (H.264)"))
                        if check_encoder_support('hevc_nvenc'):
                            available.append(("hevc_nvenc", "hevc_nvenc (H.265)"))
                        if not available:
                            available = [("none", "不支持任何NVENC编码器")]
                        return gr.update(choices=available, value=available[0][0] if available else None)
                    else:
                        available = [
                            ("libx264", "libx264 (H.264)"),
                            ("libx265", "libx265 (H.265)"),
                            ("libsvtav1", "libsvtav1 (AV1)"),
                            ("libvpx-vp9", "libvpx-vp9 (VP9)")
                        ]
                        return gr.update(choices=available, value="libx264")
                encoder_mode.change(fn=update_encoders, inputs=encoder_mode, outputs=video_encoder)

                def convert_wrapper(files, output_dir, fmt, enc_mode, enc_choice, bit_depth_val, quality_val, a_codec, a_bitrate_val, extra_args):
                    # 将中文位深选项转换为内部标识
                    depth_map = {"自动（保留原色深）": "auto", "8bit": "8bit", "10bit": "10bit"}
                    depth_key = depth_map.get(bit_depth_val, "auto")
                    yield from convert_files_general(files, output_dir, fmt, enc_mode, enc_choice, depth_key, quality_val, a_codec, a_bitrate_val, extra_args)

                btn_convert.click(
                    fn=convert_wrapper,
                    inputs=[files_convert, output_dir_convert, output_format, encoder_mode, video_encoder, bit_depth, quality, audio_codec, audio_bitrate, additional_params],
                    outputs=log_convert
                )

        gr.Markdown("---\n### 📌 使用说明\n- **递归处理**：自动扫描所有子文件夹，输出保持相同目录结构\n- **字幕配对**：优先匹配同名的`.ass`/`.srt`，语言偏好`SC`（简体）\n- **GPU要求**：10bit视频自动降级8bit（使用滤镜）避免编码失败；纯GPU转码需显卡支持对应编码器\n- **FFmpeg**：请确保`ffmpeg.exe`（Windows）或`ffmpeg`（Linux）位于同目录或PATH中")

    return demo

def main():
    demo = create_ui()
    demo.queue()
    # 自动寻找可用端口
    port = 7860
    max_port = 7900
    found_port = None
    while port <= max_port:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
            found_port = port
            break
        except OSError:
            port += 1
    if found_port is None:
        print("无法找到可用端口，将使用默认 7860（可能冲突）")
        found_port = 7860
    # 自动打开浏览器
    threading.Timer(2, lambda: webbrowser.open(f"http://localhost:{found_port}")).start()
    demo.launch(server_name="localhost", server_port=found_port, share=False)

if __name__ == "__main__":
    main()