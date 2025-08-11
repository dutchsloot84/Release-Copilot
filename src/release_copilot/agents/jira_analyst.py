from typing import List, Dict
from pydantic import BaseModel

from release_copilot.tools.jira_tools import get_jira_issues


class JiraIssues(BaseModel):
    issues: List[Dict]


def collect_jira(jql: str | None = None, fix_version: str | None = None) -> JiraIssues:
    raw = get_jira_issues(jql=jql, fix_version=fix_version)
    issues = [{'key': i.get('key'), 'summary': i.get('summary', ''), 'status': i.get('status', '')} for i in raw]
    return JiraIssues(issues=issues)
