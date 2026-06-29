@echo off
setlocal

:: Move to the folder this .bat file lives in (handles spaces in path correctly)
cd /d "%~dp0"
if errorlevel 1 (
    echo ERROR: Could not change to script directory: %~dp0
    pause
    exit /b 1
)

:: Check Python
python --version >nul 2>&1
if errorlevel 1 goto nopython

:: fraude_tray.py is now the single entry point — it starts Ollama, the proxy,
:: FraudeRepo, and Fraude Automations itself, then shows a tray icon.
if not exist "%~dp0fraude_tray.py" goto notray

:: Use pythonw (no console window) — preferred, so the tray runs silently
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" /b pythonw "%~dp0fraude_tray.py"
    goto done
)

:: pythonw not found — launch invisibly via a single-line VBScript
echo CreateObject("WScript.Shell").Run "python """ & "%~dp0fraude_tray.py" & """", 0, False > "%TEMP%\fraude_tray_launch.vbs"
start "" /b wscript "%TEMP%\fraude_tray_launch.vbs"
goto done

:notray
echo fraude_tray.py not found — falling back to starting services individually.
ollama list >nul 2>&1
if errorlevel 1 (
    start /min "" ollama serve
    timeout /t 3 /nobreak >nul
)
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" /b pythonw "%~dp0ollama_proxy.py"
    if exist "%~dp0frauderepo.py" start "" /b pythonw "%~dp0frauderepo.py"
    if exist "%~dp0fraude_automations.py" start "" /b pythonw "%~dp0fraude_automations.py"
) else (
    echo CreateObject("WScript.Shell").Run "python """ & "%~dp0ollama_proxy.py" & """", 0, False > "%TEMP%\fraude_proxy.vbs"
    start "" /b wscript "%TEMP%\fraude_proxy.vbs"
)
goto done

:nopython
echo Python not found. Install from python.org
pause
exit /b 1

:done
echo Fraude services starting. Look for the blue F icon in your system tray
echo (click the ^^ arrow near the clock to show hidden icons if needed).
timeout /t 2 /nobreak >nul
endlocal
