from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from release_copilot.kit.errors import ConfigError


@dataclass
class ConfigData:
    """Structured representation of the JSON config file."""

    repos: Dict[str, str]
    release_branch: Optional[str] = None
    develop_branch: Optional[str] = None
    fix_version: Optional[str] = None
    llm_model: Optional[str] = None


def load_config(path: str | Path) -> ConfigData:
    """Load and validate the JSON configuration file.

    Parameters
    ----------
    path:
        Path to the JSON file.

    Returns
    -------
    ConfigData
        Parsed configuration.

    Raises
    ------
    ConfigError
        If the file is missing or invalid.
    """

    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid JSON: {exc}") from exc

    repos = data.get("repos") or {}
    if not isinstance(repos, dict) or not repos:
        raise ConfigError("Config must include a 'repos' mapping")

    release_branch = data.get("release_branch")
    develop_branch = data.get("develop_branch")
    fix_version = data.get("fix_version")
    llm_model = data.get("llm_model")
    if not (release_branch or develop_branch):
        raise ConfigError("Config must define 'release_branch' or 'develop_branch'")

    return ConfigData(
        repos=repos,
        release_branch=release_branch,
        develop_branch=develop_branch,
        fix_version=fix_version,
        llm_model=llm_model,
    )
