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
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
IGNORE_DIRS = {'output', 'fonts', 'python', '__pycache__'}

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v'}
SUBTITLE_EXTENSIONS = {'.ass', '.srt'}
PREFERRED_LANG = 'SC'

def random_str(k=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=k))

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

def create_temp_work_dir():
    temp_base = 'C:\\temp'
    os.makedirs(temp_base, exist_ok=True)
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

def process_video(video_path, subtitle_path, output_subdir):
    rel_output_dir = os.path.join(OUTPUT_DIR, output_subdir)
    os.makedirs(rel_output_dir, exist_ok=True)
    video_basename = os.path.basename(video_path)
    name_without_ext = os.path.splitext(video_basename)[0]
    output_path = os.path.join(rel_output_dir, f"{name_without_ext}_hardsub.mp4")
    if os.path.exists(output_path):
        print(f"  跳过: {output_path}")
        return True

    work_dir = create_temp_work_dir()
    try:
        temp_video = os.path.join(work_dir, "video.mp4")
        temp_sub = os.path.join(work_dir, "sub.ass")
        create_hardlink_or_copy(video_path, temp_video)
        shutil.copy2(subtitle_path, temp_sub)

        original_cwd = os.getcwd()
        os.chdir(work_dir)

        vf_filter = "subtitles=sub.ass"

        cmd = [
            FFMPEG_PATH,
            '-i', 'video.mp4',
            '-vf', vf_filter,
            '-c:v', 'libx264',      # CPU 编码，稳定可靠
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            'output_temp.mp4'
        ]

        print(f"  🔄 CPU处理中: {video_basename}")
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
    print("=== 动漫字幕烧录工具 (CPU稳定版) ===")
    print(f"工作目录: {BASE_DIR}")
    if not os.path.isfile(FFMPEG_PATH):
        print(f"错误: 找不到 ffmpeg.exe，请放在 {BASE_DIR} 目录下")
        sys.exit(1)
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