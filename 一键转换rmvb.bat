@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置输出根目录
set "OUTPUT_ROOT=output"
if not exist "%OUTPUT_ROOT%" mkdir "%OUTPUT_ROOT%"

:: FFmpeg 路径（请按实际情况修改）
set "FFMPEG=.\ffmpeg.exe"
if not exist "%FFMPEG%" set "FFMPEG=ffmpeg"

echo ================================================
echo 批量递归转换 RMVB → MP4（自动适配新旧显卡）
echo ================================================

:: 检测 NVIDIA 显卡
set "USE_NVENC=0"
set "CUDA_MAJOR=0"
for /f "tokens=3" %%i in ('nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2^>nul') do (
    for /f "delims=." %%a in ("%%i") do set "CUDA_MAJOR=%%a"
    if !CUDA_MAJOR! GEQ 5 set "USE_NVENC=1"
)
if !USE_NVENC! equ 1 (
    echo ✓ 启用 NVENC 硬件加速
) else (
    echo ℹ 使用 CPU 软件编码
)

echo.
echo 开始递归转换所有子文件夹中的 .rmvb 文件...
echo.

:: 递归遍历所有 .rmvb 文件
for /r . %%a in (*.rmvb) do (
    set "input=%%a"
    set "relpath=%%~pa"
    :: 去掉开头的当前目录前缀（.\）
    set "relpath=!relpath:.=!"
    if "!relpath!"=="" set "relpath=\"
    if "!relpath:~0,1!"=="\" set "relpath=!relpath:~1!"
    
    set "outdir=%OUTPUT_ROOT%\!relpath!"
    if not exist "!outdir!" mkdir "!outdir!"
    
    echo [转换中] "%%a"
    if !USE_NVENC! equ 1 (
        "%FFMPEG%" -hwaccel cuda -i "%%a" ^
            -map 0 -c:v h264_nvenc -preset p4 -cq 23 ^
            -c:a aac -b:a 192k -movflags +faststart ^
            "!outdir!\%%~na.mp4" -y
    ) else (
        "%FFMPEG%" -i "%%a" ^
            -c:v libx264 -preset medium -crf 23 ^
            -c:a aac -b:a 192k -movflags +faststart ^
            "!outdir!\%%~na.mp4" -y
    )
    
    if !errorlevel! equ 0 (
        echo   ✓ 成功
    ) else (
        echo   ✗ 失败
    )
    echo.
)

echo ================================================
echo 全部完成！输出文件位于 %OUTPUT_ROOT% 文件夹内，并保持原目录结构。
echo ================================================
pause