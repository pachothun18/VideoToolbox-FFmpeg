"""GPU + CPU video transcode tabs."""
import gradio as gr
from app.config import BASE_DIR
from app.ui.common import AUDIO_BITRATES, parse_gpu_index, update_bitrates, max_workers_slider


def _run_gpu_trans(d, o, f, c, ac, ab, gpu, workers_val):
    gpu_index, hwaccel_type = parse_gpu_index(gpu)
    from app.pipeline.batch import run_batch_from_directory
    yield from run_batch_from_directory(
        d, o, force_cpu=False, with_subtitles=False, crf_value=c,
        audio_codec=ac, audio_bitrate=ab if ac != 'copy' else '192k', out_format=f,
        gpu_index=gpu_index, hwaccel_type=hwaccel_type,
        max_workers=workers_val)


def _run_cpu_trans(d, o, f, c, ac, ab, workers_val):
    from app.pipeline.batch import run_batch_from_directory
    yield from run_batch_from_directory(
        d, o, force_cpu=True, with_subtitles=False, crf_value=c,
        audio_codec=ac, audio_bitrate=ab if ac != 'copy' else '192k', out_format=f,
        max_workers=workers_val)


def build(gpu_selector):

    with gr.TabItem("GPU视频转码"):
        with gr.Row():
            input_dir = gr.Textbox(label="输入目录", value=str(BASE_DIR))
            output_dir = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_gpu_trans"))
        with gr.Row():
            out_fmt = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
            crf = gr.Slider(label="CQ (质量)", minimum=10, maximum=35, step=1, value=23)
        with gr.Row():
            audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
            audio_br = gr.Dropdown(label="音频比特率", choices=AUDIO_BITRATES, value="192k")
        with gr.Row():
            workers_gpu = max_workers_slider()
        btn = gr.Button("开始处理", variant="primary")
        log = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
        audio_codec.change(fn=update_bitrates, inputs=audio_codec, outputs=audio_br)
        btn.click(fn=_run_gpu_trans, inputs=[input_dir, output_dir, out_fmt, crf, audio_codec, audio_br, gpu_selector, workers_gpu], outputs=log)

    with gr.TabItem("CPU视频转码"):
        with gr.Row():
            input_dir = gr.Textbox(label="输入目录", value=str(BASE_DIR))
            output_dir = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_cpu_trans"))
        with gr.Row():
            out_fmt = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
            crf = gr.Slider(label="CRF (质量)", minimum=10, maximum=35, step=1, value=23)
        with gr.Row():
            audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
            audio_br = gr.Dropdown(label="音频比特率", choices=AUDIO_BITRATES, value="192k")
        with gr.Row():
            workers_cpu = max_workers_slider()
        btn = gr.Button("开始处理", variant="primary")
        log = gr.Textbox(label="处理日志", lines=20, autoscroll=True)
        audio_codec.change(fn=update_bitrates, inputs=audio_codec, outputs=audio_br)
        btn.click(fn=_run_cpu_trans, inputs=[input_dir, output_dir, out_fmt, crf, audio_codec, audio_br, workers_cpu], outputs=log)