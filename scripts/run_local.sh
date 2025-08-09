#!/bin/bash
set -e
if [ ! -f .env ]; then
  python -m src.config.env_wizard
fi
python -m src.app "$@"
if [ $? -eq 0 ]; then
  echo "Outputs written to data/outputs" && \
  xdg-open data/outputs >/dev/null 2>&1 || open data/outputs >/dev/null 2>&1 || true
fi
