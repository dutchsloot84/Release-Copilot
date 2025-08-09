from typing import List, Dict
from pydantic import BaseModel

from src.tools.jira_tools import get_jira_issues_for_fixversion


class JiraIssues(BaseModel):
    issues: List[Dict]


def collect_jira(fix_version: str) -> JiraIssues:
    raw = get_jira_issues_for_fixversion(fix_version)
    issues = [{'key': i.get('key'), 'summary': i.get('fields', {}).get('summary', '')} for i in raw]
    return JiraIssues(issues=issues)
