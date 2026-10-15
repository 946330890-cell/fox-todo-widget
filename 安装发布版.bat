@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0安装发布版.ps1"
if errorlevel 1 (
    echo 安装失败，请查看上面的提示。
    pause
    exit /b 1
)

echo 安装完成，桌面快捷方式已经创建。
pause
