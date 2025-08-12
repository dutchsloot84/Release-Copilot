from release_copilot.agents import jira_analyst


def test_collect_jira(monkeypatch):
    def fake_get_jira_issues(jql=None, fix_version=None):
        return [
            {"key": "ABC-1", "summary": "Issue", "status": "Done", "extra": "x"}
        ]

    monkeypatch.setattr(jira_analyst, "get_jira_issues", fake_get_jira_issues)

    result = jira_analyst.collect_jira("jql", "1.0")
    assert result.issues == [{"key": "ABC-1", "summary": "Issue", "status": "Done"}]
