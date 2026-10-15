@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Project virtual environment not found. Run the dependency installer first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo 正在安装发布版打包工具...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-input --timeout 30 --retries 1 -r requirements-build.txt
if errorlevel 1 (
        echo Failed to install the packaging tool.
        pause
        exit /b 1
    )
)

if exist "release" rmdir /s /q "release"
if exist "build\pyinstaller" rmdir /s /q "build\pyinstaller"

echo Building the standalone Windows release...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name FoxTodoWidget --distpath "release" --workpath "build\pyinstaller" --specpath "." --add-data "assets;assets" "main.py"
if errorlevel 1 (
    echo Release build failed.
    pause
    exit /b 1
)

copy /y "install.bat" "release\install.bat" >nul
copy /y "install.ps1" "release\install.ps1" >nul
copy /y "release-notes.txt" "release\release-notes.txt" >nul

echo.
echo Release created in the release folder.
echo Zip the complete release folder and share it.
echo The recipient should extract it and run install.bat.
pause
