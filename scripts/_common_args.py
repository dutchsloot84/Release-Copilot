from __future__ import annotations
import json, shlex
from pathlib import Path
from typing import Dict, List

LAST_PATH = Path("data/.last_run.json")
LAST_PATH.parent.mkdir(parents=True, exist_ok=True)

def save_last(args: List[str]) -> None:
    LAST_PATH.write_text(json.dumps({"args": args}, indent=2), encoding="utf-8")

def load_last() -> List[str] | None:
    if LAST_PATH.exists():
        try:
            data = json.loads(LAST_PATH.read_text(encoding="utf-8"))
            return data.get("args")
        except Exception:
            return None
    return None

def build_args(
    *,
    config_path: str,
    release_only: bool,
    develop_only: bool,
    fix_version: str | None,
    write_llm: bool,
    llm_model: str,
    llm_budget_cents: int,
    force_refresh: bool,
) -> List[str]:
    args: List[str] = [
        "-m", "release_copilot.commands.audit_from_config",
        "--config", config_path,
        "--cache-ttl-hours", "12",
    ]
    if release_only:
        args.append("--release-only")
    elif develop_only:
        args.append("--develop-only")
    # If neither, process both branches (default)

    if force_refresh:
        args.append("--force-refresh")

    if fix_version:
        args += ["--fix-version", fix_version]

    # Reports are on by default; LLM summary is opt-in
    if write_llm:
        args += ["--write-llm-summary", "--llm-model", llm_model, "--llm-budget-cents", str(llm_budget_cents)]

    return args
