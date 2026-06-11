#!/bin/bash
# 视频工具箱 Linux 启动脚本

cd "$(dirname "$0")"

# 检测 Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请安装 Python 3.8+"
    exit 1
fi

PYTHON_CMD="python3"

# 安装/更新依赖
if [ -f "requirements.txt" ]; then
    echo "正在检查/安装 requirements.txt 中的依赖..."
    $PYTHON_CMD -m pip install -r requirements.txt --quiet
else
    echo "未找到 requirements.txt，尝试安装 gradio..."
    $PYTHON_CMD -c "import gradio" &> /dev/null
    if [ $? -ne 0 ]; then
        $PYTHON_CMD -m pip install gradio --quiet
    fi
fi

# 检查 ffmpeg（可选）
if ! command -v ffmpeg &> /dev/null; then
    echo "警告: 未找到 ffmpeg，请安装 ffmpeg 以确保转码功能正常"
fi

# 后台启动服务（Python 会自动打开浏览器）
echo "启动视频工具箱..."
$PYTHON_CMD video_toolbox.py &
PID=$!

echo "工具箱已启动，PID=$PID。浏览器将自动打开。关闭此终端不会停止服务。"