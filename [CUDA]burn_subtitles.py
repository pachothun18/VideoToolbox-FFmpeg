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
FFPROBE_PATH = os.path.join(BASE_DIR, "ffprobe.exe")   # 可选，用于更精确检测
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IGNORE_DIRS = {'output', 'fonts', 'python', '__pycache__'}

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v'}
SUBTITLE_EXTENSIONS = {'.ass', '.srt'}
PREFERRED_LANG = 'SC'   # 字幕语言偏好

# ====== 编码器能力检测 ======
def check_encoder_support(encoder_name):
    """检查 FFmpeg 是否支持指定的编码器"""
    cmd = [FFMPEG_PATH, '-encoders']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return encoder_name in result.stdout

def get_nvidia_gpu_info():
    """通过 nvidia-smi 获取 GPU 型号和驱动版本（可选）"""
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
    """返回 (codec_name, pix_fmt)"""
    # 优先使用 ffprobe
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
    # 回退：解析 ffmpeg -i 输出
    cmd = [FFMPEG_PATH, '-i', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    stderr = result.stderr
    # 匹配类似 "Video: h264, yuv420p10le"
    match = re.search(r'Video: (?:[^,]+), ([^,]+), ([^,]+)', stderr)
    if match:
        codec_name = match.group(1).split()[0]
        pix_fmt = match.group(2).strip()
        return codec_name, pix_fmt
    return None, None

# ====== 文件配对 ======
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

# ====== 核心处理 ======
def process_video(video_path, subtitle_path, output_subdir):
    rel_output_dir = os.path.join(OUTPUT_DIR, output_subdir)
    os.makedirs(rel_output_dir, exist_ok=True)
    video_basename = os.path.basename(video_path)
    name_without_ext = os.path.splitext(video_basename)[0]
    output_path = os.path.join(rel_output_dir, f"{name_without_ext}_hardsub.mp4")
    if os.path.exists(output_path):
        print(f"  跳过: {output_path}")
        return True

    # 获取视频信息
    codec, pix_fmt = get_video_info(video_path)
    is_10bit = pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le')
    print(f"  📊 视频信息: 编码={codec}, 色深={'10bit' if is_10bit else '8bit'}")

    # 决定编码策略
    # 检测可用的GPU编码器
    has_h264_nvenc = check_encoder_support('h264_nvenc')
    has_hevc_nvenc = check_encoder_support('hevc_nvenc')

    if is_10bit:
        # 10bit 视频: 优先尝试 hevc_nvenc (需要GPU支持10bit编码)
        if has_hevc_nvenc:
            encoder = 'hevc_nvenc'
            output_pix_fmt = 'p010le'
            profile = 'main10'
            use_gpu = True
            print(f"  🚀 使用 GPU (HEVC 10bit) 编码")
        else:
            # 不支持HEVC硬件编码，回退到CPU libx264
            encoder = 'libx264'
            output_pix_fmt = None   # libx264 会自动保留10bit? 不，默认输出8bit，需要指定
            # 对于10bit输入，libx264可以输出10bit，需要添加 -pix_fmt yuv420p10le
            output_pix_fmt = 'yuv420p10le'
            profile = 'high10'
            use_gpu = False
            print(f"  💻 使用 CPU (libx264 10bit) 编码")
    else:
        # 8bit 视频: 优先 h264_nvenc，其次 hevc_nvenc，最后 libx264
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
            encoder = 'libx264'
            output_pix_fmt = 'yuv420p'
            profile = None
            use_gpu = False
            print(f"  💻 使用 CPU (libx264) 编码")

    work_dir = create_temp_work_dir()
    try:
        temp_video = os.path.join(work_dir, "video.mp4")
        temp_sub = os.path.join(work_dir, "sub.ass")
        create_hardlink_or_copy(video_path, temp_video)
        shutil.copy2(subtitle_path, temp_sub)

        original_cwd = os.getcwd()
        os.chdir(work_dir)

        # 构建命令
        cmd = []
        if use_gpu:
            cmd.extend([FFMPEG_PATH, '-hwaccel', 'cuda', '-i', 'video.mp4'])
        else:
            cmd.extend([FFMPEG_PATH, '-i', 'video.mp4'])

        cmd.extend(['-vf', "subtitles=sub.ass"])
        cmd.extend(['-c:v', encoder])
        if profile:
            cmd.extend(['-profile:v', profile])
        if output_pix_fmt:
            cmd.extend(['-pix_fmt', output_pix_fmt])

        # 质量参数
        if encoder == 'libx264':
            cmd.extend(['-crf', '23'])
        elif encoder == 'h264_nvenc':
            cmd.extend(['-cq', '23'])
        elif encoder == 'hevc_nvenc':
            cmd.extend(['-rc', 'vbr', '-cq', '23'])

        cmd.extend(['-c:a', 'aac', '-b:a', '128k', '-y', 'output_temp.mp4'])

        print(f"  🔄 处理中: {video_basename}")
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
                for line in result.stderr.strip().split('\n')[-5:]:
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

def main():
    os.chdir(BASE_DIR)
    print("=== 通用N卡CUDA字幕烧录工具 ===")
    print(f"工作目录: {BASE_DIR}")

    # 检查 FFmpeg
    if not os.path.isfile(FFMPEG_PATH):
        print(f"错误: 找不到 ffmpeg.exe，请放在 {BASE_DIR} 目录下")
        sys.exit(1)

    # 显示GPU信息（如果有）
    gpu_name, driver = get_nvidia_gpu_info()
    if gpu_name:
        print(f"检测到显卡: {gpu_name} (驱动 {driver})")
    else:
        print("未检测到NVIDIA显卡或nvidia-smi不可用，将使用CPU回退")

    # 检查编码器支持情况
    print("编码器支持情况:")
    print(f"  h264_nvenc: {'✓' if check_encoder_support('h264_nvenc') else '✗'}")
    print(f"  hevc_nvenc: {'✓' if check_encoder_support('hevc_nvenc') else '✗'}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pairs = find_all_video_subtitle_pairs(BASE_DIR)
    if not pairs:
        print("未找到匹配的视频和字幕文件对。")
        sys.exit(1)

    print(f"找到 {len(pairs)} 个文件对，开始处理...\n")
    success = 0
    for video, sub, rel_dir in pairs:
        print(f"视频: {os.path.relpath(video, BASE_DIR)}")
        print(f"字幕: {os.path.relpath(sub, BASE_DIR)}")
        if process_video(video, sub, rel_dir):
            success += 1
        print()
    print(f"=== 完成，成功: {success}/{len(pairs)} ===")

if __name__ == "__main__":
    main()