@echo off
setlocal
cd /d "%~dp0"
wscript.exe "%~dp0launch_hidden.vbs"
exit /b 0
