@echo off
echo ========================================
echo Not Whisper Flow - Quick Start
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo Python found!
echo.

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import whisper; import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Dependencies not installed. Running installation...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Dependencies OK!
echo.

REM Check if setup has been run
if not exist "%USERPROFILE%\.whisper_flow\config.json" (
    echo.
    echo First-time setup required...
    echo.
    python -m utils.installer
    if errorlevel 1 (
        echo.
        echo ERROR: Setup failed
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo Starting Not Whisper Flow...
echo ========================================
echo.
echo Tray icon: microphone in system tray
echo Hotkey: Ctrl+Shift+Space (start/stop recording)
echo Modes: Code Prompt / Voice Notes (switch via tray menu)
echo.

python main.py

pause
