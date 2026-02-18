@echo off
setlocal

REM ============================================================
REM Not Whisper Flow - Windows launcher (no console window)
REM ============================================================

REM Use pythonw from the venv if it exists, otherwise system pythonw
set PYTHONW=%~dp0venv\Scripts\pythonw.exe
set PYTHON=%~dp0venv\Scripts\python.exe

if not exist "%PYTHONW%" (
    set PYTHONW=pythonw
    set PYTHON=python
)

REM Quick dependency check using the visible python
"%PYTHON%" -c "import whisper, customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    "%PYTHON%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM First-time setup check
if not exist "%USERPROFILE%\.whisper_flow\config.json" (
    echo Running first-time setup...
    "%PYTHON%" -m utils.installer
)

REM Launch WITHOUT a console window
start "" "%PYTHONW%" "%~dp0main.py"

endlocal
