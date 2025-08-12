from types import SimpleNamespace

from release_copilot.commands.audit_from_config import _clean_fix_version, resolve_jql


def test_clean_fix_version_trims_quotes_and_space():
    raw = ' " Mobilitas 2025.08.22 " '
    assert _clean_fix_version(raw) == "Mobilitas 2025.08.22"
    assert _clean_fix_version(None) is None


def test_resolve_jql_cleans_fix_version():
    args = SimpleNamespace(jql=None, fix_version=' "Mobilitas 2025.08.22" ')
    settings = SimpleNamespace(default_jql='fixVersion = "{fix_version}" AND issuetype = "Automation "')
    jql = resolve_jql(args, settings)
    assert '"Mobilitas 2025.08.22"' in jql
    assert '" Mobilitas 2025.08.22"' not in jql  # no leading space inside quotes


def test_resolve_jql_passthrough_jql():
    args = SimpleNamespace(jql=' project = ABC ', fix_version=None)
    settings = SimpleNamespace(default_jql=None)
    jql = resolve_jql(args, settings)
    assert jql == 'project = ABC'
