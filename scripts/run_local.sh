#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing/validating dependencies..."
pip3 install -r requirements.txt >/dev/null 2>&1 || pip install -r requirements.txt >/dev/null 2>&1
echo "Installing package in editable mode..."
pip3 install -e . >/dev/null 2>&1 || pip install -e . >/dev/null 2>&1

# Ensure .env
if [ ! -f ".env" ]; then
  echo "No .env found. Launching first-run wizard..."
  python3 -m release_copilot.config.env_wizard || python -m release_copilot.config.env_wizard
fi

# Pass-through if args present
if [ $# -gt 0 ]; then
  echo
  echo "Running: python -m release_copilot.commands.audit_from_config $*"
  python -m release_copilot.commands.audit_from_config "$@"
  EC=$?
else
  # Interactive guided run
  has_last=$(python - <<'PY'
from scripts._common_args import load_last
import sys
sys.stdout.write('1' if load_last() else '0')
PY
)

  if [ "$has_last" = "1" ]; then
    read -r -p "Run with last settings? (y/N) " USE_LAST
    if [[ "${USE_LAST:-N}" =~ ^[Yy]$ ]]; then
      RUNLINE=$(python - <<'PY'
from scripts._common_args import load_last
import shlex
args = load_last() or []
print(shlex.join(args))
PY
)
      echo
      echo "Running: python $RUNLINE"
      eval "python $RUNLINE"
      EC=$?
      goto_end=true
    fi
  fi

  if [ "${goto_end:-false}" != "true" ]; then
    # pick first config under config/*.json
    CONFIG=$(ls -1 config/*.json 2>/dev/null | head -n1 || true)
    if [ -z "$CONFIG" ]; then
      echo "No config JSON found under config/*.json"
      exit 1
    fi
    echo "Using config: $CONFIG"

    IFS=$'\n' read -r REL_BRANCH DEV_BRANCH CFG_FIX CFG_LLM <<EOF
$(python - <<PY "$CONFIG"
import json,sys
cfg=json.load(open(sys.argv[1]))
print(cfg.get("release_branch",""))
print(cfg.get("develop_branch",""))
print(cfg.get("fix_version",""))
print(cfg.get("llm_model","gpt-4o-mini"))
PY)
EOF

    read -r -p "Branch mode [release ($REL_BRANCH)/develop ($DEV_BRANCH)/both] (default both): " BRANCH_MODE
    BRANCH_MODE=${BRANCH_MODE:-both}

    read -r -p "Fix Version (optional, default $CFG_FIX): " FIX_VERSION
    FIX_VERSION=${FIX_VERSION:-$CFG_FIX}

    read -r -p "Write LLM narrative? (y/N) " WRITE_LLM
    if [[ "${WRITE_LLM:-N}" =~ ^[Yy]$ ]]; then
      read -r -p "Model [$CFG_LLM]: " LLM_MODEL
      LLM_MODEL=${LLM_MODEL:-$CFG_LLM}
      read -r -p "Budget (cents) [8]: " LLM_BUDGET
      LLM_BUDGET=${LLM_BUDGET:-8}
    else
      LLM_MODEL=$CFG_LLM
      LLM_BUDGET=8
    fi

    read -r -p "Force refresh caches? (y/N) " FORCE_REFRESH

    echo
    echo "--- Summary ---"
    echo "Config: $CONFIG"
    echo "Branch mode: $BRANCH_MODE (release=$REL_BRANCH, develop=$DEV_BRANCH)"
    echo "Fix Version: ${FIX_VERSION:-<none>}"
    echo "LLM narrative: ${WRITE_LLM:-N} (model=$LLM_MODEL, budget=${LLM_BUDGET}c)"
    echo "Force refresh: ${FORCE_REFRESH:-N}"
    echo

    RUNLINE=$(CONFIG="$CONFIG" BRANCH_MODE="$BRANCH_MODE" FIX_VERSION="$FIX_VERSION" WRITE_LLM="$WRITE_LLM" LLM_MODEL="$LLM_MODEL" LLM_BUDGET="$LLM_BUDGET" FORCE_REFRESH="$FORCE_REFRESH" python - <<'PY'
from scripts._common_args import build_args, save_last
import os, shlex
config = os.environ.get("CONFIG") or ""
release_only = (os.environ.get("BRANCH_MODE","both").lower()=="release")
develop_only = (os.environ.get("BRANCH_MODE","both").lower()=="develop")
fix_version = os.environ.get("FIX_VERSION") or None
write_llm = (os.environ.get("WRITE_LLM","N").lower().startswith("y"))
llm_model = os.environ.get("LLM_MODEL","gpt-4o-mini")
llm_budget = int(os.environ.get("LLM_BUDGET","8") or "8")
force_refresh = (os.environ.get("FORCE_REFRESH","N").lower().startswith("y"))
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
print(shlex.join(args))
PY
)
    echo
    echo "Running: python $RUNLINE"
    eval "python $RUNLINE"
    EC=$?
  fi
fi

# Open outputs folder on success
if [ ${EC:-1} -eq 0 ]; then
  if [ -d "data/outputs" ]; then
    case "$(uname | tr '[:upper:]' '[:lower:]')" in
      darwin*) open "data/outputs" ;;
      linux*) xdg-open "data/outputs" >/dev/null 2>&1 || true ;;
      *) : ;;
    esac
  fi
else
  echo "Run failed with exit code ${EC}."
fi
exit ${EC:-1}
