@echo off
chcp 65001 >nul
.\python\python.exe "%~dp0一键转换mkv.py"
if %errorlevel% equ 0 (
    echo 成功
) else (
    echo 不成功
)
pause