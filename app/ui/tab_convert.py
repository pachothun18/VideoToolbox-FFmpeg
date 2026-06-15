"""General video conversion tab."""
import gradio as gr
from app.config import BASE_DIR
from app.commands.profiles import (
    EncoderProfile,
    get_available_gpu_profiles, CPU_PROFILES, get_profile,
)
from app.ui.common import AUDIO_BITRATES, parse_gpu_index, update_bitrates, max_workers_slider


def _gpu_encoder_names():
    return [p.name for p in get_available_gpu_profiles()]


def _cpu_encoder_names():
    return [p.name for p in CPU_PROFILES]


def _resolve_encoder(name: str) -> EncoderProfile:
    p = get_profile(name)
    if p is not None:
        return p
    return EncoderProfile(
        name=name, label=name,
        use_gpu=False, hwaccel=None,
        default_pix_fmt='yuv420p', supports_10bit=False, pix_fmt_10bit=None,
        quality_param='crf', rate_control=[],
    )


def build(gpu_selector):
    with gr.TabItem("通用视频转换"):
        gr.Markdown("拖拽或点击添加视频文件，可选择输出格式、编码器、质量参数、输出位深等。")

        with gr.Row():
            files_input = gr.File(label="选择视频文件（支持批量）", file_count="multiple", file_types=None)
            output_dir = gr.Textbox(label="输出目录", value=str(BASE_DIR / "output_convert"))

        with gr.Row():
            output_format = gr.Dropdown(label="输出格式", choices=["mp4", "mkv", "mov", "avi", "webm", "flv"], value="mp4")
            encoder_mode = gr.Radio(label="编码模式", choices=["GPU", "CPU"], value="GPU")

        init_choices = ["自动"] + _gpu_encoder_names()
        if not _gpu_encoder_names():
            init_choices = ["自动"] + _cpu_encoder_names()

        with gr.Row():
            video_encoder = gr.Dropdown(
                label="视频编码器", choices=init_choices, value="自动",
                interactive=True, allow_custom_value=True)
            bit_depth = gr.Dropdown(
                label="色深",
                choices=["自动", "8bit", "10bit"],
                value="自动")
            chroma = gr.Dropdown(
                label="色度采样 (YUV)",
                choices=["自动", "4:2:0", "4:2:2", "4:4:4"],
                value="自动")
            quality = gr.Slider(label="质量 (CRF/CQ)", minimum=10, maximum=35, step=1, value=23)

        with gr.Row():
            audio_codec = gr.Dropdown(label="音频编码器", choices=["aac", "mp3", "copy", "libopus"], value="aac")
            audio_bitrate = gr.Dropdown(label="音频比特率", choices=AUDIO_BITRATES, value="192k")

        with gr.Row():
            workers = max_workers_slider()
            additional_params = gr.Textbox(label="额外FFmpeg参数（可选）", placeholder="例如: -preset fast -tune film")

        btn = gr.Button("开始转换", variant="primary")
        log = gr.Textbox(label="转换日志", lines=20, autoscroll=True)

        def update_encoders(mode):
            if mode == "GPU":
                names = ["自动"] + _gpu_encoder_names()
                return gr.update(choices=names, value="自动")
            else:
                names = ["自动"] + _cpu_encoder_names()
                return gr.update(choices=names, value="自动")

        encoder_mode.change(fn=update_encoders, inputs=encoder_mode, outputs=video_encoder)

        audio_codec.change(fn=update_bitrates, inputs=audio_codec, outputs=audio_bitrate)

        def _run_convert(files, out_dir, fmt, enc_mode, enc_choice, depth_label, chroma_label, quality_val, a_codec, a_bitrate, extra, gpu, workers_val):
            depth_map = {"自动": "auto", "8bit": "8bit", "10bit": "10bit"}
            chroma_map = {"自动": "auto", "4:2:0": "420", "4:2:2": "422", "4:4:4": "444"}
            encoder = None if enc_choice == "自动" else _resolve_encoder(enc_choice)
            bitrate = a_bitrate if a_codec != "copy" else "192k"
            gpu_index, hwaccel_type = parse_gpu_index(gpu)
            from app.pipeline.batch import run_general_convert
            yield from run_general_convert(
                files, out_dir, fmt, encoder,
                depth_map.get(depth_label, "auto"),
                chroma_map.get(chroma_label, "auto"),
                quality_val, a_codec, bitrate, extra,
                gpu_index=gpu_index, hwaccel_type=hwaccel_type,
                max_workers=workers_val,
            )

        btn.click(
            fn=_run_convert,
            inputs=[files_input, output_dir, output_format, encoder_mode,
                    video_encoder, bit_depth, chroma, quality, audio_codec, audio_bitrate, additional_params, gpu_selector, workers],
            outputs=log)