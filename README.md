
# 视频处理工具箱 (Video Toolbox)

基于 Gradio 的 WebUI 视频处理工具，支持 GPU/CPU 字幕烧录、视频转码、批量处理、格式转换等功能。
提供 **Python 源码版** 和 **Windows 便携版**（无需安装 Python，解压即用）。

---

## 主要功能

- **GPU/CPU 字幕烧录**：自动匹配同名字幕（ASS/SRT），支持 GPU 加速
- **GPU/CPU 视频转码**：递归处理子目录，保持原有目录结构
- **批量上传文件**：拖拽或点击添加多个视频，自动查找同名字幕
- **通用视频转换**：自定义输出格式、编码器、质量、位深、色度采样
- **10bit 视频智能处理**：若显卡不支持 10bit 编码，自动转为 8bit 并保持 GPU 加速
- **跨平台支持**：自动检测 Windows/Linux/macOS，选择正确的 ffmpeg 路径；Linux 支持 VAAPI，macOS 支持 VideoToolbox 硬件加速
- **多任务并发处理**：自动检测 CPU 核心数，默认 3 个任务并行，用户可自定义并发数（上限为 CPU 核心数）
- **CPU 线程自动分配**：多任务时按 `CPU核心 / 并发数` 自动设置 `-threads` 参数，避免线程争抢
- **实时日志输出**：显示转码进度和 FFmpeg 详细错误信息

---

## 版本说明

| 版本 | 适用系统 | 运行方式 | 下载 |
|------|----------|----------|------|
| **源码版** | Windows / Linux / macOS | 需要 Python 3.8+ | 克隆本仓库 |
| **便携版** | Windows 10/11 | 解压即用，无需 Python 和 FFmpeg | 从 [Releases](../../releases) 下载 zip 压缩包 |

---

## 源码版使用方法

### 1. 环境准备

- 安装 **Python 3.8+**（[官网下载](https://python.org)）
- 安装 **FFmpeg**（见下方 [FFmpeg 获取与配置](#ffmpeg-获取与配置)）

### 2. 克隆仓库

```bash
git clone https://github.com/pachothun18/VideoToolbox-FFmpeg.git
cd VideoToolbox-FFmpeg
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行

- **Windows**：双击 `启动WebUI.bat`
- **Linux**：在终端执行 `bash 启动WebUI.sh`
- **macOS**：在终端执行 `bash 启动WebUI.sh`（见下方 [macOS 注意事项](#macos-注意事项)）

首次运行时会自动检查并安装依赖，浏览器将自动打开 `http://localhost:7860`。

---

## 便携版使用方法

1. 从 [Releases](../../releases) 下载 zip 压缩包
2. 解压到任意文件夹（建议路径不含中文或空格）
3. 双击 `VideoToolbox.exe` 运行
4. 浏览器将自动打开 `http://localhost:7860`

> **提示**：便携版已内置 Python 运行时和 FFmpeg，无需额外安装任何依赖。

压缩包内容说明：

```
VideoToolbox/
├── VideoToolbox.exe    ← 主程序（已集成 Python 运行时及依赖库）
├── ffmpeg.exe          ← FFmpeg（已内置）
├── ffprobe.exe         ← FFmpeg 分析工具
├── ffplay.exe          ← FFmpeg 播放器
└── *.dll               ← FFmpeg 运行时库
```

---

## 多任务并发处理

程序默认以 3 个任务并行执行，每个标签页底部都有一个"并行任务数"滑块，可在 1 到 CPU 核心数之间调整。

### 并发数建议

| 使用场景 | 建议并发数 | 说明 |
|----------|-----------|------|
| GPU 编码 (NVENC/VAAPI) | 1-3 | GPU 编码器硬件级并行，过多任务可能导致显存不足 |
| CPU 编码 (libx264/libx265) | CPU核心数/4 到 CPU核心数/2 | 软件编码吃 CPU，过多任务反而降低单任务效率 |
| 字幕烧录 (GPU) | 1-2 | 字幕烧录需要 CPU 解析字幕 + GPU 编码，混合负载 |

### CPU 线程自动分配

多任务并发时，程序会自动按以下公式为每个 ffmpeg 进程设置 `-threads` 参数：

```
threads = max(1, CPU核心数 // 并发数)
```

例如 16 核 CPU 跑 4 个任务，每个任务分配 4 个线程，总线程数 16，不超载。

单任务时（并发数=1）不设置 `-threads`，由 ffmpeg 自动选择最优线程数。

---

## FFmpeg 获取与配置

本工具依赖 FFmpeg 实现所有音视频处理。

> **便携版用户无需操作**，FFmpeg 已内置在压缩包中。

### 源码版用户

#### Windows

推荐从以下站点下载：

- [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) – 提供完整版（默认 GPL 许可证）
- [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) – 同时提供 **GPL** 和 **LGPL** 版本

下载后解压，将 `bin` 文件夹内的 `ffmpeg.exe` 和 `ffprobe.exe` 复制到与 `video_toolbox.py` 相同的目录下，或添加到系统 PATH 环境变量。

#### Linux

通过系统包管理器安装：

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg

# Fedora
sudo dnf install ffmpeg
```

程序会自动检测系统 ffmpeg（`shutil.which("ffmpeg")`），若本地存在无后缀的 `ffmpeg` 文件则优先使用。Windows 的 `.exe` 文件在 Linux 上会被自动跳过。

### Linux 硬件加速

程序在 Linux 上支持以下 GPU 加速方案：

- **NVIDIA CUDA (NVENC)**：`h264_nvenc`、`hevc_nvenc`，需安装 NVIDIA 驱动和 CUDA 版 ffmpeg
- **VAAPI**（Intel/AMD）：`h264_vaapi`、`hevc_vaapi`，需安装 `vaapi` 驱动（`sudo apt install intel-media-va-driver` 或 `mesa-va-drivers`）

程序会自动检测可用编码器，优先级顺序为 `CUDA -> VAAPI -> AMF -> QSV -> VideoToolbox -> CPU(软编码)`。

---

## macOS 注意事项

> ⚠️ **macOS 支持为实验性功能，未经充分测试。**

### Intel Mac（x86）

- 程序可通过 `system_profiler SPDisplaysDataType` 检测 AMD 独显和 Intel 核显
- 硬件加速使用 **VideoToolbox**（`h264_videotoolbox` / `hevc_videotoolbox`），支持 H.264 和 H.265 编码
- 10bit 视频需 HEVC VideoToolbox 支持（Apple T2 芯片及更新机型）

### Apple Silicon（ARM）

- 程序自动识别 GPU 厂商为 `apple`，使用 VideoToolbox 框架
- 支持 `h264_videotoolbox`、`hevc_videotoolbox`（含 10bit）
- 性能优于 Intel Mac，编码质量与系统原生一致

### 通用说明

- 使用 `bash 启动WebUI.sh` 启动，该脚本会自动创建虚拟环境并安装依赖
- 确保系统已安装 FFmpeg（`brew install ffmpeg`），或放置无后缀的 `ffmpeg` 可执行文件到项目目录
- macOS 上暂不支持 CUDA/NVENC、AMF、QSV、VAAPI，仅 VideoToolbox 和软件编码可用

---

## 许可证

本项目使用 [MIT License](LICENSE)。
**FFmpeg 是其各自所有者的项目，遵循 LGPL/GPL 许可证，与本项目独立。**

---

## 使用的开源项目

本项目便携版压缩包中内置了 FFmpeg，在此展示所用版本及源码和许可证链接

FFmpeg (LGPL variant, autobuild-2026-06-11-14-22)
- 许可证：LGPLv3
- 源代码：https://github.com/FFmpeg/FFmpeg/archive/d30dead35e7fecae51ccd4602273153c87b1bbd9.zip
- 许可证原文：https://github.com/FFmpeg/FFmpeg/blob/master/COPYING.LGPLv3

项目所使用的 Python 库

| 名称              | 版本号     | 许可证                              |
|-------------------|-------------|--------------------------------------|
| Jinja2            | 3.1.6       | BSD License                          |
| MarkupSafe        | 3.0.3       | BSD-3-Clause                         |
| PyYAML            | 6.0.3       | MIT License                          |
| Pygments          | 2.20.0      | BSD-2-Clause                         |
| annotated-doc     | 0.0.4       | MIT                                  |
| annotated-types   | 0.7.0       | MIT License                          |
| anyio             | 4.13.0      | MIT                                  |
| brotli            | 1.2.0       | MIT                                  |
| certifi           | 2026.5.20   | Mozilla Public License 2.0 (MPL 2.0) |
| click             | 8.4.1       | BSD-3-Clause                         |
| colorama          | 0.4.6       | BSD License                          |
| exceptiongroup    | 1.3.1       | MIT License                          |
| fastapi           | 0.136.3     | MIT                                  |
| filelock          | 3.29.3      | MIT                                  |
| fsspec            | 2026.4.0    | BSD-3-Clause                         |
| gradio            | 6.17.3      | Apache-2.0                           |
| gradio_client     | 2.5.0       | Apache-2.0                           |
| groovy            | 0.1.2       | MIT License                          |
| h11               | 0.16.0      | MIT License                          |
| hf-gradio         | 0.4.1       | MIT                                  |
| hf-xet            | 1.5.1       | Apache-2.0                           |
| httpcore          | 1.0.9       | BSD-3-Clause                         |
| httpx             | 0.28.1      | BSD License                          |
| huggingface_hub   | 1.19.0      | Apache Software License              |
| idna              | 3.18        | BSD-3-Clause                         |
| markdown-it-py    | 4.2.0       | MIT License                          |
| mdurl             | 0.1.2       | MIT License                          |
| numpy             | 2.2.6       | BSD License                          |
| orjson            | 3.11.9      | MPL-2.0 AND (Apache-2.0 OR MIT)      |
| packaging         | 26.2        | Apache-2.0 OR BSD-2-Clause           |
| pandas            | 2.3.3       | BSD License                          |
| pillow            | 12.2.0      | MIT-CMU                              |
| pydantic          | 2.13.4      | MIT                                  |
| pydantic_core     | 2.46.4      | MIT                                  |
| pydub             | 0.25.1      | MIT License                          |
| python-dateutil   | 2.9.0.post0 | Apache Software License; BSD License |
| python-multipart  | 0.0.32      | Apache-2.0                           |
| pytz              | 2026.2      | MIT License                          |
| rich              | 15.0.0      | MIT License                          |
| safehttpx         | 0.1.7       | MIT License                          |
| semantic-version  | 2.10.0      | BSD License                          |
| shellingham       | 1.5.4       | ISC License (ISCL)                   |
| six               | 1.17.0      | MIT License                          |
| starlette         | 1.3.0       | BSD-3-Clause                         |
| tomlkit           | 0.14.0      | MIT License                          |
| tqdm              | 4.68.2      | MPL-2.0 AND MIT                      |
| typer             | 0.25.1      | MIT                                  |
| typing-inspection | 0.4.2       | MIT                                  |
| typing_extensions | 4.15.0      | PSF-2.0                              |
| tzdata            | 2026.2      | Apache-2.0                           |
| uvicorn           | 0.49.0      | BSD-3-Clause                         |
