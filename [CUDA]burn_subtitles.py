import os
import sys

# 嵌入式Python环境默认不会将脚本自身路径加入 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.core.filesystem import find_all_video_subtitle_pairs
from app.core.ffmpeg import check_encoder_support, get_video_info
from app.core.gpu import get_nvidia_gpu_info
from app.commands.profiles import H264_NVENC, HEVC_NVENC, LIBX264
from app.pipeline.job import run_job

OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def select_encoder_and_params(video_path):
    codec, pix_fmt = get_video_info(video_path)
    is_10bit = pix_fmt in ('yuv420p10le', 'yuv422p10le', 'yuv444p10le', 'p010le', 'p010')
    has_h264 = check_encoder_support('h264_nvenc')
    has_hevc = check_encoder_support('hevc_nvenc')

    if is_10bit:
        if has_hevc:
            return HEVC_NVENC, 'p010le', 'main10', "GPU (HEVC 10bit)"
        else:
            return LIBX264, 'yuv420p10le', 'high10', "CPU (libx264 10bit)"
    else:
        if has_h264:
            return H264_NVENC, 'yuv420p', None, "GPU (H.264)"
        elif has_hevc:
            return HEVC_NVENC, 'yuv420p', None, "GPU (HEVC)"
        else:
            return LIBX264, 'yuv420p', None, "CPU (libx264)"


def main():
    os.chdir(BASE_DIR)
    print("=== 通用N卡CUDA字幕烧录工具 ===")
    print(f"工作目录: {BASE_DIR}")

    gpu_name, driver = get_nvidia_gpu_info()
    if gpu_name:
        print(f"检测到显卡: {gpu_name} (驱动 {driver})")
    else:
        print("未检测到NVIDIA显卡或nvidia-smi不可用，将使用CPU回退")

    print("编码器支持情况:")
    print(f"  h264_nvenc: {'Y' if check_encoder_support('h264_nvenc') else 'N'}")
    print(f"  hevc_nvenc: {'Y' if check_encoder_support('hevc_nvenc') else 'N'}")

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

        out_subdir = os.path.join(OUTPUT_DIR, rel_dir)
        os.makedirs(out_subdir, exist_ok=True)
        name_without_ext = os.path.splitext(os.path.basename(video))[0]
        output_path = os.path.join(out_subdir, f"{name_without_ext}_hardsub.mp4")

        if os.path.exists(output_path):
            print(f"  跳过: {output_path}")
            success += 1
            print()
            continue

        encoder, pix_fmt, profile, msg = select_encoder_and_params(video)
        print(f"  {msg} 编码: {os.path.basename(video)}")

        ok, logs = run_job(video, output_path, encoder, quality=23, audio_codec='aac',
                           audio_bitrate='128k', sub_path=sub, output_pix_fmt=pix_fmt, profile=profile)
        for log in logs:
            print(f"  {log}")
        if ok:
            success += 1
        print()

    print(f"=== 完成，成功: {success}/{len(pairs)} ===")


if __name__ == "__main__":
    main()
