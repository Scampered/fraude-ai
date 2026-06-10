@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 ( echo Python not found. & pause & exit /b 1 )
python -c "import pystray" >nul 2>&1
if errorlevel 1 ( pip install pystray pillow --quiet )
start "" pythonw ollama_proxy.py --tray
timeout /t 2 /nobreak >nul
