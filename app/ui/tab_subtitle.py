"""GPU + CPU subtitle burning tabs."""
import gradio as gr
from app.config import BASE_DIR
from app.pipeline.batch import run_batch_from_directory

AUDIO_BITRATES = ["96k", "128k", "160k", "192k", "256k", "320k", "384k", "448k", "512k"]


def _update_bitrates(codec):
    if codec == "mp3":
        return gr.update(choices=AUDIO_BITRATES[:6], value="128k", interactive=True)
    elif codec == "copy":
        return gr.update(choices=["N/A (copy)"], value="N/A (copy)", interactive=False)
    else:
        return gr.update(choices=AUDIO_BITRATES, value="128k", interactive=True)


def _run_gpu_sub(d, o, f, c, ac, ab):
    yield from run_batch_from_directory(
        d, o, force_cpu=False, with_subtitles=True, crf_value=c,
        audio_codec=ac, audio_bitrate=ab if ac != 'copy' else '128k', out_format=f)


def _run_cpu_sub(d, o, f, c, ac, ab):
    yield from run_batch_from_directory(
        d, o, force_cpu=True, with_subtitles=True, crf_value=c,
        audio_codec=ac, audio_bitrate=ab if ac != 'copy' else '128k', out_format=f)


def build():
    with gr.TabItem("GPU字幕烧录"):
        with gr.Row():
            input_dir = gr.Textbox(label="输入目录", value=str(BASE_DIR))
            output_dir = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_gpu_sub"))
        with gr.Row():
            out_fmt = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
            crf = gr.Slider(label="CQ (质量)", minimum=10, maximum=35, step=1, value=23)
        with gr.Row():
            audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
            audio_br = gr.Dropdown(label="音频比特率", choices=AUDIO_BITRATES, value="128k")
        btn = gr.Button("开始处理", variant="primary")
        log = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
        audio_codec.change(fn=_update_bitrates, inputs=audio_codec, outputs=audio_br)
        btn.click(fn=_run_gpu_sub, inputs=[input_dir, output_dir, out_fmt, crf, audio_codec, audio_br], outputs=log)

    with gr.TabItem("CPU字幕烧录"):
        with gr.Row():
            input_dir = gr.Textbox(label="输入目录", value=str(BASE_DIR))
            output_dir = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_cpu_sub"))
        with gr.Row():
            out_fmt = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
            crf = gr.Slider(label="CRF (质量)", minimum=10, maximum=35, step=1, value=23)
        with gr.Row():
            audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
            audio_br = gr.Dropdown(label="音频比特率", choices=AUDIO_BITRATES, value="128k")
        btn = gr.Button("开始处理", variant="primary")
        log = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
        audio_codec.change(fn=_update_bitrates, inputs=audio_codec, outputs=audio_br)
        btn.click(fn=_run_cpu_sub, inputs=[input_dir, output_dir, out_fmt, crf, audio_codec, audio_br], outputs=log)
