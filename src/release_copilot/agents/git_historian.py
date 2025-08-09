from typing import List, Dict, Optional
from pydantic import BaseModel

from release_copilot.tools.bitbucket_tools import get_commits_by_branch


class Commits(BaseModel):
    commits: List[Dict]


def collect_commits(project: str, repo: str, branch: str, since: Optional[str] = None) -> Commits:
    raw = get_commits_by_branch(project, repo, branch, since)
    commits = []
    for c in raw:
        commits.append({
            'id': c.get('id'),
            'message': c.get('message'),
            'author': (c.get('author') or {}).get('name') if isinstance(c.get('author'), dict) else c.get('author'),
            'jira_keys': c.get('jira_keys', [])
        })
    return Commits(commits=commits)
