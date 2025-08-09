#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# ---- Optional venv (uncomment to enable)
# if [ ! -d ".venv" ]; then
#   echo "Creating virtual environment..."
#   python3 -m venv .venv || python -m venv .venv
# fi
# # shellcheck source=/dev/null
# source .venv/bin/activate

echo "Installing/validating dependencies..."
if ! pip3 install -r requirements.txt >/dev/null 2>&1; then
  pip install -r requirements.txt >/dev/null 2>&1
fi

if [ ! -f ".env" ]; then
  echo "No .env found. Launching first-run wizard..."
  python3 -m src.config.env_wizard || python -m src.config.env_wizard
fi

echo "Starting Streamlit UI..."
exec streamlit run src/ui/streamlit_app.py  # add --server.port 8502 to change port
