import os

import gradio as gr

AUDIO_BITRATES = ["96k", "128k", "160k", "192k", "256k", "320k", "384k", "448k", "512k"]


def get_cpu_count() -> int:
    return os.cpu_count() or 4


def get_default_workers() -> int:
    return min(3, get_cpu_count())


def max_workers_slider() -> gr.Slider:
    cpu_cores = get_cpu_count()
    default = get_default_workers()
    return gr.Slider(
        label=f"并行任务数（CPU核心: {cpu_cores}）",
        minimum=1, maximum=cpu_cores, step=1, value=default,
    )


def parse_gpu_index(gpu_value: str | None) -> tuple[int | None, str | None]:
    if not gpu_value:
        return None, None
    try:
        parts = gpu_value.split(':')
        return int(parts[0]), parts[1] if len(parts) > 1 else None
    except (ValueError, IndexError):
        return None, None


def update_bitrates(codec: str, default: str = "192k"):
    if codec == "mp3":
        return gr.update(choices=AUDIO_BITRATES[:6], value=default, interactive=True)
    elif codec == "copy":
        return gr.update(choices=["N/A (copy)"], value="N/A (copy)", interactive=False)
    else:
        return gr.update(choices=AUDIO_BITRATES, value=default, interactive=True)