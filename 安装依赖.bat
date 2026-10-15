@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv ".venv"
    ) else (
        python -m venv ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo 未找到 Python 3。请先安装 Python 3.10 或更高版本，并勾选 Add Python to PATH。
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo 依赖安装完成。现在可以双击“启动狐狸待办.bat”。
pause
