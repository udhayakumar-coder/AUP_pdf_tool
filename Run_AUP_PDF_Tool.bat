@echo off
title AUP PDF Tool - 74-in-1 Local Server
cd /d "%~dp0"

echo ==================================================
echo   AUP PDF Tool (74-in-1) - Local Windows Launcher
echo ==================================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] First-time setup: Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Python not found. Install Python 3.10+ from python.org and check "Add to PATH".
        pause
        exit /b 1
    )
    echo [2/2] Installing required Python packages...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Package installation failed. Check internet connection and retry.
        pause
        exit /b 1
    )
)

echo Starting AUP PDF Tool at http://localhost:8501 ...
".venv\Scripts\streamlit.exe" run app.py --server.headless false
pause
