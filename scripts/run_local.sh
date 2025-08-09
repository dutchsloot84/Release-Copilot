#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing/validating dependencies..."
if ! pip3 install -r requirements.txt >/dev/null 2>&1; then
  pip install -r requirements.txt >/dev/null 2>&1 || pip install -r requirements.txt
fi

echo "Installing package in editable mode..."
if ! pip3 install -e . >/dev/null 2>&1; then
  pip install -e . >/dev/null 2>&1 || pip install -e .
fi

# Ensure .env exists
if [ ! -f ".env" ]; then
  echo "No .env found. Launching first-run wizard..."
  python3 -m release_copilot.config.env_wizard || python -m release_copilot.config.env_wizard
fi

echo "Running Release Copilot (CLI)..."
exec python3 -m release_copilot.app "$@"

