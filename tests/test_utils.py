from release_copilot.tools.bitbucket_tools import extract_jira_keys
from release_copilot.agents.report_writer import compare_jira_and_commits


def test_extract_jira_keys():
    msg = 'Implement feature ABC-123 and fix BUG-9'
    keys = extract_jira_keys(msg)
    assert keys == ['ABC-123', 'BUG-9']


def test_compare_logic():
    jira = [{'key': 'ABC-1', 'summary': 'Issue'}]
    commits = [{'id': 'c1', 'author': 'dev', 'jira_keys': ['ABC-1']}]
    matches, missing, orphan = compare_jira_and_commits(jira, commits)
    assert len(matches) == 1
    assert missing == []
    assert orphan == []
