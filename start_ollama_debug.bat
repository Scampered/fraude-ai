@echo off
cd /d "%~dp0"
echo Fraude Ollama Proxy - Debug Mode
echo Press Ctrl+C to stop.
echo.
python ollama_proxy.py
pause
