
# 🎬 视频处理工具箱 (Video Toolbox)

基于 Gradio 的 WebUI 视频处理工具，支持 GPU/CPU 字幕烧录、视频转码、批量处理、格式转换等功能。  
提供 **Python 源码版** 和 **Windows 独立 EXE 版**（无需安装 Python）。

---

##  主要功能

-  **GPU/CPU 字幕烧录**：自动匹配同名字幕（ASS/SRT），支持 GPU 加速
-  **GPU/CPU 视频转码**：递归处理子目录，保持原有目录结构
-  **批量上传文件**：拖拽或点击添加多个视频，自动查找同名字幕
-  **通用视频转换**：自定义输出格式、编码器、质量、位深（8bit / 10bit / 自动）
-  **10bit 视频智能处理**：若显卡不支持 10bit 编码，自动转为 8bit 并保持 GPU 加速
-  **WebUI 界面**：自动打开浏览器，支持 Windows / Linux
-  **实时日志输出**：显示转码进度和 FFmpeg 详细错误信息

---

## 📦 版本说明

| 版本 | 适用系统 | 运行方式 | 下载 |
|------|----------|----------|------|
| **源码版** | Windows / Linux | 需要 Python 3.8+ | 克隆本仓库 |
| **EXE 版** | Windows 10/11 | 双击运行，无需 Python | 从 [Releases](../../releases) 下载 `VideoToolbox.exe` |

---

## 🔧 源码版使用方法

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

`requirements.txt` 内容如下：
```
gradio==6.17.3
huggingface_hub==1.19.0
groovy==0.1.2
safehttpx==0.1.7
hf-gradio==0.4.1
gradio-client==2.5.0
```

### 4. 运行

- **Windows**：双击 `启动WebUI.bat`
- **Linux**：在终端执行 `bash 启动WebUI.sh`

首次运行时会自动检查并安装依赖，浏览器将自动打开 `http://localhost:7860`。

---

##  EXE 版使用方法

1. 从 [Releases](../../releases) 下载 `VideoToolbox.exe`
2. 下载 **FFmpeg** 可执行文件（见下方说明），将 `ffmpeg.exe` 和 `ffprobe.exe` 与 `VideoToolbox.exe` 放在**同一文件夹**
3. 双击 `VideoToolbox.exe` 运行，浏览器自动打开

> **注意**：EXE 版本不需要 Python 环境，但必须自行提供 FFmpeg。

---

##  FFmpeg 获取与配置

本工具依赖 FFmpeg 实现所有音视频处理。请根据您的系统下载对应版本：

### Windows 用户

推荐从以下两个站点下载**完整版**（包含 NVENC 支持）：

- [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) – 选择 `ffmpeg-release-full.7z` 或 `ffmpeg-release-full.zip`
- [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) – 选择 `ffmpeg-master-latest-win64-gpl.zip`

> 注意：请勿下载 `ffmpeg-master-latest-win64-gpl-shared.zip`（动态链接版），请使用 **`-gpl`** 版本。

下载后解压，将 `bin` 文件夹内的 `ffmpeg.exe` 和 `ffprobe.exe` 复制到与主程序（`video_toolbox.py` 或 `VideoToolbox.exe`）相同的目录下，或添加到系统 PATH 环境


##  许可证

本项目使用 [MIT License](LICENSE)。
