@echo off
if not exist .env (
  python -m src.config.env_wizard
)
python -m src.app %*
if %errorlevel% equ 0 (
  echo Outputs written to data/outputs
  start data/outputs
)
