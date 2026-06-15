"""Batch file upload tab."""
from functools import partial
import gradio as gr
from app.config import BASE_DIR, VIDEO_EXTENSIONS
from app.ui.common import AUDIO_BITRATES, parse_gpu_index, update_bitrates as _common_update_bitrates, max_workers_slider


def _run_upload(files, out_dir, mode, fmt, crf_val, ac, ab, gpu, workers_val):
    mode_key = "subtitle" if mode == "字幕烧录（需同名字幕）" else "transcode"
    gpu_index, hwaccel_type = parse_gpu_index(gpu)
    from app.pipeline.batch import run_batch_from_files
    yield from run_batch_from_files(files, out_dir, None, mode_key, crf_val,
                                    audio_codec=ac, audio_bitrate=ab if ac != 'copy' else '128k',
                                    out_format=fmt, gpu_index=gpu_index, hwaccel_type=hwaccel_type,
                                    max_workers=workers_val)


def build(gpu_selector):
    with gr.TabItem("批量上传文件"):
        gr.Markdown("拖拽或点击添加多个视频文件。程序会自动查找同名字幕，并输出到指定目录。")
        with gr.Row():
            files_input = gr.File(label="拖拽或点击添加视频文件", file_count="multiple", file_types=list(VIDEO_EXTENSIONS))
            output_dir = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_upload"))
        with gr.Row():
            mode_radio = gr.Radio(label="处理模式", choices=["转码（无字幕）", "字幕烧录（需同名字幕）"], value="转码（无字幕）")
            out_fmt = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
            crf = gr.Slider(label="CRF/CQ (质量)", minimum=10, maximum=35, step=1, value=23)
        with gr.Row():
            audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
            audio_br = gr.Dropdown(label="音频比特率", choices=AUDIO_BITRATES, value="128k")
        with gr.Row():
            workers = max_workers_slider()
        log = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
        btn = gr.Button("开始处理", variant="primary")

        audio_codec.change(fn=partial(_common_update_bitrates, default="128k"), inputs=audio_codec, outputs=audio_br)
        btn.click(fn=_run_upload, inputs=[files_input, output_dir, mode_radio, out_fmt, crf, audio_codec, audio_br, gpu_selector, workers], outputs=log)