# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import re
import shutil
import random
import string

# ====== 配置 ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(BASE_DIR, "ffprobe.exe")   # 可选
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IGNORE_DIRS = {'output', 'fonts', 'python', '__pycache__'}

# 支持的视频扩展名（可按需修改）
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.flv', '.wmv', '.m4v'}

# ====== 编码器能力检测 ======
def check_encoder_support(encoder_name):
    cmd = [FFMPEG_PATH, '-encoders']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return encoder_name in result.stdout

def get_nvidia_gpu_info():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'],
                                capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            name, driver = result.stdout.strip().split(',')
            return name.strip(), driver.strip()
    except:
        pass
    return None, None

# ====== 视频信息检测 ======
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
    # 回退解析 ffmpeg -i
    cmd = [FFMPEG_PATH, '-i', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    stderr = result.stderr
    match = re.search(r'Video: (?:[^,]+), ([^,]+), ([^,]+)', stderr)
    if match:
        codec_name = match.group(1).split()[0]
        pix_fmt = match.group(2).strip()
        return codec_name, pix_fmt
    return None, None

# ====== 收集所有视频文件（递归）======
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

# ====== 临时目录 ======
def create_temp_work_dir():
    temp_base = 'C:\\temp'
    os.makedirs(temp_base, exist_ok=True)
    job_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
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

# ====== 核心转码函数（无字幕）======
def convert_video(video_path, output_subdir):
    rel_output_dir = os.path.join(OUTPUT_DIR, output_subdir)
    os.makedirs(rel_output_dir, exist_ok=True)
    video_basename = os.path.basename(video_path)
    name_without_ext = os.path.splitext(video_basename)[0]
    output_path = os.path.join(rel_output_dir, f"{name_without_ext}.mp4")
    if os.path.exists(output_path):
        print(f"  跳过: {output_path}")
        return True

    # 获取视频信息
    codec, pix_fmt = get_video_info(video_path)
    is_10bit = pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le')
    print(f"  📊 视频信息: 编码={codec}, 像素格式={pix_fmt}, 色深={'10bit' if is_10bit else '8bit'}")

    # 检测可用的 GPU 编码器
    has_h264_nvenc = check_encoder_support('h264_nvenc')
    has_hevc_nvenc = check_encoder_support('hevc_nvenc')

    # 决定编码策略（完全硬件，不降级）
    if is_10bit:
        if has_hevc_nvenc:
            encoder = 'hevc_nvenc'
            output_pix_fmt = 'p010le'
            profile = 'main10'
            use_gpu = True
            print(f"  🚀 使用 GPU (HEVC 10bit) 编码")
        else:
            print(f"  ❌ 错误: 10bit 视频但显卡不支持 hevc_nvenc 编码。无法使用纯硬件加速。")
            return False
    else:
        if has_h264_nvenc:
            encoder = 'h264_nvenc'
            output_pix_fmt = 'yuv420p'
            profile = None
            use_gpu = True
            print(f"  🚀 使用 GPU (H.264) 编码")
        elif has_hevc_nvenc:
            encoder = 'hevc_nvenc'
            output_pix_fmt = 'yuv420p'
            profile = None
            use_gpu = True
            print(f"  🚀 使用 GPU (HEVC) 编码")
        else:
            print(f"  ❌ 错误: 未找到任何 NVENC 编码器，无法使用硬件加速。")
            return False

    work_dir = create_temp_work_dir()
    try:
        # 只复制原视频，不复制字幕
        temp_video = os.path.join(work_dir, "input_video" + os.path.splitext(video_path)[1])
        create_hardlink_or_copy(video_path, temp_video)

        original_cwd = os.getcwd()
        os.chdir(work_dir)

        # 构建命令（去掉 subtitles 滤镜）
        cmd = [FFMPEG_PATH, '-hwaccel', 'cuda', '-i', os.path.basename(temp_video)]
        cmd.extend(['-c:v', encoder])
        if profile:
            cmd.extend(['-profile:v', profile])
        if output_pix_fmt:
            cmd.extend(['-pix_fmt', output_pix_fmt])

        # 质量参数
        if encoder == 'h264_nvenc':
            cmd.extend(['-cq', '23'])
        elif encoder == 'hevc_nvenc':
            cmd.extend(['-rc', 'vbr', '-cq', '23'])

        cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-y', 'output_temp.mp4'])

        print(f"  🔄 转码中: {video_basename}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        os.chdir(original_cwd)

        if result.returncode == 0:
            temp_output = os.path.join(work_dir, 'output_temp.mp4')
            shutil.move(temp_output, output_path)
            print(f"  ✅ 成功: {output_path}")
            return True
        else:
            print(f"  ❌ 失败: {video_basename}")
            if result.stderr:
                for line in result.stderr.strip().split('\n')[-8:]:
                    print(f"    {line}")
            return False
    except Exception as e:
        print(f"  ⚠️ 异常: {video_basename} - {e}")
        return False
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except:
            pass

# ====== 主函数 ======
def main():
    os.chdir(BASE_DIR)
    print("=== 纯硬件加速转码（去除字幕烧录版本）===")
    print(f"工作目录: {BASE_DIR}")

    if not os.path.isfile(FFMPEG_PATH):
        print(f"错误: 找不到 ffmpeg.exe，请放在 {BASE_DIR} 目录下")
        sys.exit(1)

    gpu_name, driver = get_nvidia_gpu_info()
    if gpu_name:
        print(f"检测到显卡: {gpu_name} (驱动 {driver})")
    else:
        print("未检测到 NVIDIA 显卡，硬件加速将失败。")
        sys.exit(1)

    print("编码器支持情况:")
    print(f"  h264_nvenc: {'✓' if check_encoder_support('h264_nvenc') else '✗'}")
    print(f"  hevc_nvenc: {'✓' if check_encoder_support('hevc_nvenc') else '✗'}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    videos = find_all_videos(BASE_DIR)
    if not videos:
        print("未找到任何支持格式的视频文件。")
        sys.exit(1)

    print(f"找到 {len(videos)} 个视频文件，开始转码...\n")
    success = 0
    for video, rel_dir in videos:
        print(f"文件: {os.path.relpath(video, BASE_DIR)}")
        if convert_video(video, rel_dir):
            success += 1
        print()
    print(f"=== 完成，成功: {success}/{len(videos)} ===")
    input("按回车键退出...")

if __name__ == "__main__":
    main()