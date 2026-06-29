@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
"%PYTHON_EXE%" main.py --headless --continuous-play --allow-multiple --mute --overlay-port 8765
