import json
import pytest

from release_copilot.kit.errors import ConfigError
from release_copilot.tools.config_loader import load_config


def test_load_config_valid(tmp_path):
    data = {
        "repos": {"STARSYSONE/policycenter": "PC"},
        "release_branch": "release/r-55.0",
        "develop_branch": "develop",
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(data))
    cfg = load_config(p)
    assert cfg.repos["STARSYSONE/policycenter"] == "PC"
    assert cfg.release_branch == "release/r-55.0"
    assert cfg.develop_branch == "develop"


def test_load_config_invalid(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text("{}")
    with pytest.raises(ConfigError):
        load_config(p)
