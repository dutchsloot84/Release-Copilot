@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

REM ---- Optional venv (uncomment to enable)
REM if not exist ".venv" (
REM   echo Creating virtual environment...
REM   python -m venv .venv || (
REM     echo Failed to create virtual environment.
REM     pause >nul
REM     exit /b 1
REM   )
REM )
REM call .venv\Scripts\activate

echo Installing/validating dependencies...
pip install -r requirements.txt >nul 2>&1 || (
  echo Failed to install dependencies. Ensure Python and pip are on PATH.
  pause >nul
  exit /b 1
)

if not exist ".env" (
  echo No .env found. Launching first-run wizard...
  python -m src.config.env_wizard || (
    echo Wizard failed. Please fix credentials and retry.
    pause >nul
    exit /b 1
  )
)

echo Starting Streamlit UI...
streamlit run src/ui/streamlit_app.py
REM To change port, add: --server.port 8502
set EXITCODE=%ERRORLEVEL%
endlocal & exit /b %EXITCODE%
