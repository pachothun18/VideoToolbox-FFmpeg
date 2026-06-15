"""视频处理工具箱 - Gradio WebUI."""
import gradio as gr
from app import _gpus as _cached_gpus


def _detect_gpu_and_encoders():
    gpus = _cached_gpus
    if not gpus:
        return "未检测到GPU（仅CPU模式）", "无硬件加速编码器"

    status_parts = []
    enc_parts = []
    for gpu in gpus:
        label = f"{gpu.vendor.upper()} {gpu.name} (驱动 {gpu.driver})"
        enc_summary = " | ".join(f"{e}: {'OK' if e in gpu.encoders else '--'}" for e in gpu.encoders)
        status_parts.append(label)
        enc_parts.append(f"[{gpu.vendor.upper()}] {enc_summary}")

    return f"GPU: {'; '.join(status_parts)}", ' | '.join(enc_parts)


def _build_gpu_choices():
    gpus = _cached_gpus
    if not gpus:
        return [], None
    choices = [(gpu.label, gpu.value) for gpu in gpus]
    default = gpus[0].value if gpus else None
    return choices, default


def create_ui():
    with gr.Blocks() as demo:
        gr.Markdown("# 视频处理工具箱")
        gr.Markdown("支持GPU/CPU字幕烧录、GPU/CPU视频转码。递归处理子目录，保持原有结构。")

        with gr.Row():
            gpu_status, enc_status = _detect_gpu_and_encoders()
            gr.Markdown(f"**系统状态**：{gpu_status} &nbsp;&nbsp; {enc_status}")

        gpu_choices, gpu_default = _build_gpu_choices()
        with gr.Row():
            if gpu_choices:
                gpu_selector = gr.Dropdown(
                    label="选择GPU（用于硬件加速）",
                    choices=gpu_choices,
                    value=gpu_default,
                    interactive=True,
                    scale=2,
                )
            else:
                gpu_selector = gr.Dropdown(
                    label="选择GPU（未检测到GPU，仅CPU模式）",
                    choices=[],
                    value=None,
                    interactive=False,
                    scale=2,
                )
            gr.Markdown("", scale=1)

        from app.ui import tab_subtitle, tab_transcode, tab_upload, tab_convert
        with gr.Tabs():
            tab_subtitle.build(gpu_selector)
            tab_transcode.build(gpu_selector)
            tab_upload.build(gpu_selector)
            tab_convert.build(gpu_selector)

        gr.Markdown("""---
### 使用说明
- **递归处理**：自动扫描所有子文件夹，输出保持相同目录结构
- **字幕配对**：优先匹配同名的`.ass`/`.srt`，语言偏好`SC`（简体）
- **GPU要求**：10bit视频自动降级8bit（使用滤镜）避免编码失败；纯GPU转码需显卡支持对应编码器
- **FFmpeg**：请确保`ffmpeg.exe`（Windows）或`ffmpeg`（Linux）位于同目录或PATH中
- **多GPU**：如系统有多张显卡，可在上方下拉框中选择要使用的GPU""")

    return demo