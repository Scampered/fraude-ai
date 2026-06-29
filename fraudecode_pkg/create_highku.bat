@echo off
echo Creating HighKu model for Fraude AI...
echo This only needs to be done once.
echo.
ollama create highku -f "%~dp0highku_modelfile.txt"
if errorlevel 1 (
    echo Failed. Make sure Ollama is running: ollama serve
    pause
    exit /b 1
)
echo.
echo Success! HighKu model created.
echo In fraudecode, run: /setup
echo Set Ollama Model to: highku
pause
