@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

REM --- Dependencies (quiet) ---
echo Installing/validating dependencies...
pip install -r requirements.txt >nul 2>&1 || (
  echo Failed to install requirements. Ensure Python and pip are on PATH.
  pause & exit /b 1
)
echo Installing package in editable mode...
pip install -e . >nul 2>&1 || (
  echo Editable install failed. Check pyproject.toml and try again.
  pause & exit /b 1
)

REM --- Ensure .env ---
if not exist ".env" (
  echo No .env found. Launching first-run wizard...
  python -m release_copilot.config.env_wizard || (
    echo Wizard failed. Please fix credentials and retry.
    pause & exit /b 1
  )
)

REM If args were provided, bypass interactive flow
if not "%~1"=="" goto :RUN_WITH_ARGS

REM --- Interactive guided run ---
set "CHOICE="
set "USE_LAST=N"
set "CONFIG="
set "BRANCH_MODE=both"
set "FIX_VERSION="
set "WRITE_LLM=N"
set "LLM_MODEL=gpt-4o-mini"
set "LLM_BUDGET=8"
set "FORCE_REFRESH=N"

REM Offer last run
for /f "usebackq tokens=2 delims=:, {}" %%A in (`python - <<PY
from scripts._common_args import load_last
print({"has_last": bool(load_last())})
PY`) do set HAS_LAST=%%A

if /I "%HAS_LAST%"=="True" (
  echo.
  set /p USE_LAST=Run with last settings? (Y/N) [N]: 
  if /I "!USE_LAST!"=="Y" goto :RUN_LAST
)

echo.
echo === Select config JSON ===
for /f "delims=" %%F in ('dir /b /a:-d "config\*.json" 2^>nul') do (
  if not defined CONFIG set "CONFIG=config\%%F"
)
if not defined CONFIG (
  echo No config JSON found under config\*.json
  echo Please create one then re-run.
  pause & exit /b 1
) else (
  echo Using: %CONFIG%
)

echo.
set /p BRANCH_MODE=Branch mode [release/develop/both] (default both): 
if /I "%BRANCH_MODE%"=="" set "BRANCH_MODE=both"

echo.
set /p FIX_VERSION=Fix Version (optional, e.g., Mobilitas 2025.08.22): 

echo.
set /p WRITE_LLM=Write LLM narrative? (Y/N) [N]: 
if /I "%WRITE_LLM%"=="Y" (
  set /p LLM_MODEL=Model [gpt-4o-mini]: 
  if "%LLM_MODEL%"=="" set "LLM_MODEL=gpt-4o-mini"
  set /p LLM_BUDGET=Budget (cents) [8]: 
  if "%LLM_BUDGET%"=="" set "LLM_BUDGET=8"
)

echo.
set /p FORCE_REFRESH=Force refresh caches? (Y/N) [N]: 

echo.
echo --- Summary ---
echo Config: %CONFIG%
echo Branch mode: %BRANCH_MODE%
echo Fix Version: %FIX_VERSION%
echo LLM narrative: %WRITE_LLM% (model=%LLM_MODEL%, budget=%LLM_BUDGET%c)
echo Force refresh: %FORCE_REFRESH%
echo.

REM Build args via Python helper
python - <<PY >"%TEMP%\rc_args.txt"
from scripts._common_args import build_args, save_last
import os, json
config = r"%CONFIG%"
release_only = os.environ.get("BRANCH_MODE","both").lower()=="release"
develop_only = os.environ.get("BRANCH_MODE","both").lower()=="develop"
fix_version = os.environ.get("FIX_VERSION") or None
write_llm = (os.environ.get("WRITE_LLM","N").upper()=="Y")
llm_model = os.environ.get("LLM_MODEL","gpt-4o-mini")
llm_budget = int(os.environ.get("LLM_BUDGET","8") or "8")
force_refresh = (os.environ.get("FORCE_REFRESH","N").upper()=="Y")
args = build_args(
    config_path=config,
    release_only=release_only,
    develop_only=develop_only,
    fix_version=fix_version,
    write_llm=write_llm,
    llm_model=llm_model,
    llm_budget_cents=llm_budget,
    force_refresh=force_refresh,
)
save_last(args)
print(" ".join(args))
PY

set /p RUNLINE=<"%TEMP%\rc_args.txt"
goto :RUN_BUILT

:RUN_LAST
python - <<PY >"%TEMP%\rc_args.txt"
from scripts._common_args import load_last
args = load_last() or []
print(" ".join(args))
PY
set /p RUNLINE=<"%TEMP%\rc_args.txt"
goto :RUN_BUILT

:RUN_WITH_ARGS
set RUNLINE=-m release_copilot.commands.audit_from_config %*

:RUN_BUILT
echo.
echo Running: python %RUNLINE%
python %RUNLINE%
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% EQU 0 (
  REM Try to open outputs folder
  if exist "data\outputs" start "" explorer.exe "data\outputs"
) else (
  echo Run failed with exit code %EXITCODE%.
)

echo.
pause
endlocal & exit /b %EXITCODE%
