from app.config import FFMPEG_PATH
from app.commands.profiles import EncoderProfile


class FFmpegCommandBuilder:
    def __init__(self):
        self._cmd = [FFMPEG_PATH]
        self._vf_parts: list[str] = []
        self._gpu_index: int | None = None
        self._hwaccel_type: str | None = None

    def set_input(self, path: str, use_hwaccel: bool = False, hwaccel_type: str | None = None):
        if use_hwaccel and hwaccel_type:
            self._cmd.extend(['-hwaccel', hwaccel_type])
        self._cmd.extend(['-i', path])

    def set_video_encoder(self, encoder: EncoderProfile):
        self._cmd.extend(['-c:v', encoder.name])

    def add_video_filter(self, vf: str | None):
        if vf:
            self._vf_parts.append(vf)

    def set_profile(self, profile: str | None):
        if profile:
            self._cmd.extend(['-profile:v', profile])

    def set_output_pix_fmt(self, pix_fmt: str | None):
        if pix_fmt:
            self._cmd.extend(['-pix_fmt', pix_fmt])

    def set_quality(self, value: int, param: str = 'crf', rate_control: list[str] | None = None):
        if rate_control:
            self._cmd.extend(rate_control)
        self._cmd.extend([f'-{param}', str(value)])

    def set_audio(self, codec: str = 'aac', bitrate: str = '192k'):
        self._cmd.extend(['-c:a', codec])
        if codec != 'copy':
            self._cmd.extend(['-b:a', bitrate])

    def set_gpu_index(self, gpu_index: int | None, hwaccel_type: str | None = None):
        if gpu_index is not None:
            self._gpu_index = gpu_index
            self._hwaccel_type = hwaccel_type

    def set_extra_args(self, extra_args: str | None):
        if extra_args:
            self._cmd.extend(extra_args.split())

    def set_output(self, path: str, faststart: bool = True):
        if self._vf_parts:
            self._cmd.extend(['-vf', ','.join(self._vf_parts)])
        if faststart:
            self._cmd.extend(['-movflags', '+faststart'])
        self._cmd.extend(['-y', path])

    def build(self) -> list[str]:
        cmd = list(self._cmd)
        if self._gpu_index is not None:
            if self._hwaccel_type == 'cuda':
                cmd = self._inject_nvenc_gpu(cmd)
            elif self._hwaccel_type == 'qsv':
                cmd = self._inject_qsv_device(cmd)
        return cmd

    def _inject_nvenc_gpu(self, cmd: list[str]) -> list[str]:
        """Insert -gpu <index> after -c:v <encoder> for NVENC."""
        try:
            cv_idx = cmd.index('-c:v')
            insert_pos = cv_idx + 2
            cmd.insert(insert_pos, '-gpu')
            cmd.insert(insert_pos + 1, str(self._gpu_index))
        except ValueError:
            cmd.extend(['-gpu', str(self._gpu_index)])
        return cmd

    def _inject_qsv_device(self, cmd: list[str]) -> list[str]:
        """Insert -init_hw_device qsv=<index> before -i for QSV device selection."""
        try:
            i_idx = cmd.index('-i')
            cmd.insert(i_idx, '-init_hw_device')
            cmd.insert(i_idx + 1, f'qsv={self._gpu_index}')
        except ValueError:
            cmd.extend(['-init_hw_device', f'qsv={self._gpu_index}'])
        return cmd
