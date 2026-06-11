@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_DIR=.\python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"

:: ========== 1. 解压 Python embed 包 ==========
if not exist "%PYTHON_EXE%" (
    if not exist "python-3.12.8-embed-amd64.zip" (
        echo 错误: 未找到 python-3.12.8-embed-amd64.zip
        pause
        exit /b 1
    )
    echo 正在解压 Python ...
    powershell -Command "Expand-Archive -Path 'python-3.12.8-embed-amd64.zip' -DestinationPath '%PYTHON_DIR%' -Force"
)

:: ========== 2. 修改 python312._pth 启用 site-packages ==========
set "PTH_FILE=%PYTHON_DIR%\python312._pth"
if exist "%PTH_FILE%" (
    echo 配置 Python 以支持第三方库 ...
    powershell -Command "(Get-Content '%PTH_FILE%') -replace '#import site', 'import site' | Set-Content '%PTH_FILE%'"
)

:: ========== 3. 安装 pip ==========
if not exist "%PYTHON_DIR%\Lib\site-packages\pip" (
    if not exist "get-pip.py" (
        echo 错误: 未找到 get-pip.py
        pause
        exit /b 1
    )
    echo 正在安装 pip...
    "%PYTHON_EXE%" get-pip.py
)

:: ========== 4. 安装 requirements.txt 中的依赖 ==========
if exist "requirements.txt" (
    echo 正在安装/更新 requirements.txt 中的依赖...
    "%PYTHON_EXE%" -m pip install -r requirements.txt --no-warn-script-location
) else (
    :: 如果没有 requirements.txt，则尝试安装 gradio 最新版（兼容旧行为）
    "%PYTHON_EXE%" -c "import gradio" >nul 2>nul
    if errorlevel 1 (
        echo 未找到 requirements.txt，正在安装 gradio 最新版...
        "%PYTHON_EXE%" -m pip install gradio --no-warn-script-location
    )
)

:: ========== 5. 启动服务（后台运行） ==========
echo 启动视频工具箱，请稍候...
start /b "" "%PYTHON_EXE%" video_toolbox.py

:: 等待服务启动（约4秒）
timeout /t 4 /nobreak >nul

echo 工具箱已启动，关闭本窗口不会停止程序。
pause