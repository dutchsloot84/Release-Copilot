@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo Installing/validating dependencies...
pip install -r requirements.txt >nul 2>&1 || (
  echo Failed to install requirements. Ensure Python and pip are on PATH.
  pause >nul
  exit /b 1
)

echo Installing package in editable mode...
pip install -e . >nul 2>&1 || (
  echo Editable install failed. Check pyproject.toml and try again.
  pause >nul
  exit /b 1
)

REM Ensure .env exists
if not exist ".env" (
  echo No .env found. Launching first-run wizard...
  python -m release_copilot.config.env_wizard || (
    echo Wizard failed. Please fix credentials and retry.
    pause >nul
    exit /b 1
  )
)

echo Running Release Copilot (CLI)...
python -m release_copilot.app %*
set EXITCODE=%ERRORLEVEL%

pause
endlocal & exit /b %EXITCODE%
