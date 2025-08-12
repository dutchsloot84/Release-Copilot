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

echo.
echo [1] Guided run
echo [2] Connectivity only (Jira & Bitbucket checks)
set /p MENU=Choose an option [1]: 
if "%MENU%"=="2" goto :CONNECTIVITY_ONLY

REM --- Interactive guided run ---
set "CHOICE="
set "USE_LAST=N"
set "CONFIG="
set "BRANCH_MODE=both"
set "FIX_VERSION="
set "WRITE_LLM=N"
set "LLM_MODEL="
set "LLM_BUDGET=8"
set "FORCE_REFRESH=N"

REM Offer last run
for /f %%A in ('python -c "from scripts._common_args import load_last; import sys; sys.stdout.write('1' if load_last() else '0')"') do set HAS_LAST=%%A
if "%HAS_LAST%"=="1" (
  echo.
  set /p "USE_LAST=Run with last settings? (Y/N) [N]: "
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

for /f "delims=" %%A in ('python -c "import json,sys; cfg=json.load(open(r\"%CONFIG%\")); print('REL_BRANCH='+cfg.get('release_branch','')); print('DEV_BRANCH='+cfg.get('develop_branch','')); print('CFG_FIX_VERSION='+cfg.get('fix_version','')); print('CFG_LLM_MODEL='+cfg.get('llm_model','gpt-4o-mini'))"') do set %%A
set "LLM_MODEL=%CFG_LLM_MODEL%"

echo.
set /p "BRANCH_MODE=Branch mode [release (!REL_BRANCH!)/develop (!DEV_BRANCH!)/both] (default both): "
if /I "%BRANCH_MODE%"=="" set "BRANCH_MODE=both"

echo.
set /p "FIX_VERSION=Fix Version (optional, default !CFG_FIX_VERSION!): "
if "!FIX_VERSION!"=="" set "FIX_VERSION=!CFG_FIX_VERSION!"

echo.
set /p "WRITE_LLM=Write LLM narrative? (Y/N) [N]: "
if /I "%WRITE_LLM%"=="Y" (
  set /p "LLM_MODEL=Model [!CFG_LLM_MODEL!]: "
  if "!LLM_MODEL!"=="" set "LLM_MODEL=!CFG_LLM_MODEL!"
  set /p "LLM_BUDGET=Budget (cents) [8]: "
  if "%LLM_BUDGET%"=="" set "LLM_BUDGET=8"
)

echo.
set /p "FORCE_REFRESH=Force refresh caches? (Y/N) [N]: "

echo.
echo --- Summary ---
echo Config: %CONFIG%
echo Branch mode: %BRANCH_MODE% (release=%REL_BRANCH%, develop=%DEV_BRANCH%)
echo Fix Version: %FIX_VERSION%
echo LLM narrative: %WRITE_LLM% (model=%LLM_MODEL%, budget=%LLM_BUDGET%c)
echo Force refresh: %FORCE_REFRESH%
echo.

REM Build args via Python helper
python -c "from scripts._common_args import build_args, save_last; import os, subprocess; config=r'%CONFIG%'; release_only=os.environ.get('BRANCH_MODE','both').lower()=='release'; develop_only=os.environ.get('BRANCH_MODE','both').lower()=='develop'; fix_version=os.environ.get('FIX_VERSION') or None; write_llm=(os.environ.get('WRITE_LLM','N').upper()=='Y'); llm_model=os.environ.get('LLM_MODEL','gpt-4o-mini'); llm_budget=int(os.environ.get('LLM_BUDGET','8') or '8'); force_refresh=(os.environ.get('FORCE_REFRESH','N').upper()=='Y'); args=build_args(config_path=config, release_only=release_only, develop_only=develop_only, fix_version=fix_version, write_llm=write_llm, llm_model=llm_model, llm_budget_cents=llm_budget, force_refresh=force_refresh); save_last(args); print(subprocess.list2cmdline(args))" >"%TEMP%\rc_args.txt"

set /p RUNLINE=<"%TEMP%\rc_args.txt"
goto :RUN_BUILT

:RUN_LAST
python -c "from scripts._common_args import load_last; import subprocess; print(subprocess.list2cmdline(load_last() or []))" >"%TEMP%\rc_args.txt"
set /p RUNLINE=<"%TEMP%\rc_args.txt"
goto :RUN_BUILT

:CONNECTIVITY_ONLY
echo.
echo Running connectivity check...
python -m release_copilot.commands.audit_from_config --connectivity-only
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% EQU 0 (
  echo Connectivity: OK
) else (
  echo Connectivity: FAILED (exit %EXITCODE%)
)
echo.
pause
endlocal & exit /b %EXITCODE%

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
