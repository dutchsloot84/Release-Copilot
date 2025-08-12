from pathlib import Path

from release_copilot.agents import report_writer


def test_compare_jira_and_commits():
    jira = [
        {"key": "ABC-1", "summary": "Issue one"},
        {"key": "ABC-2", "summary": "Issue two"},
    ]
    commits = [
        {"id": "c1", "author": "Alice", "jira_keys": ["ABC-1"]},
        {"id": "c2", "author": "Bob", "jira_keys": []},
    ]

    matches, missing, no_story = report_writer.compare_jira_and_commits(jira, commits)

    assert matches == [
        {"key": "ABC-1", "summary": "Issue one", "commit": "c1", "author": "Alice"}
    ]
    assert missing == [{"key": "ABC-2", "summary": "Issue two"}]
    assert no_story == [{"id": "c2", "author": "Bob"}]


def test_write_report(tmp_path: Path):
    jira = [{"key": "ABC-1", "summary": "Issue one"}]
    commits = [{"id": "c1", "author": "Alice", "jira_keys": ["ABC-1"]}]

    report = report_writer.write_report(jira, commits, tmp_path)

    excel = tmp_path / "release_audit.xlsx"
    md = tmp_path / "release_report.md"
    assert excel.exists()
    assert md.exists()

    assert report.matches and report.artifacts["excel"] == str(excel)
