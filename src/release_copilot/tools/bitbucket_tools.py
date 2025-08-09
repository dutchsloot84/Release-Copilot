import re
from typing import List, Dict, Optional

import requests
from langchain.tools import tool
from tenacity import retry, wait_fixed, stop_after_attempt

from release_copilot.config.settings import settings
from release_copilot.kit.caching import cache_json
from release_copilot.kit.errors import ApiError

JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def extract_jira_keys(message: str) -> List[str]:
    return JIRA_KEY_RE.findall(message)


@tool
def get_commits_by_branch(project: str, repo: str, branch: str, since: Optional[str] = None) -> List[Dict]:
    """Fetch commits for a branch and tag with Jira keys."""
    return _get_commits(project, repo, branch, since)


@cache_json('bitbucket', ttl_hours=12)
@retry(wait_fixed(2), stop=stop_after_attempt(3))
def _get_commits(project: str, repo: str, branch: str, since: Optional[str] = None) -> List[Dict]:
    url = f"{settings.bitbucket_base_url}/rest/api/1.0/projects/{project}/repos/{repo}/commits"
    params = {'until': branch}
    if since:
        params['since'] = since
    resp = requests.get(url, params=params, auth=(settings.bitbucket_email, settings.bitbucket_app_password), timeout=10)
    if not resp.ok:
        raise ApiError(f"Bitbucket API error: {resp.status_code}")
    data = resp.json().get('values', [])
    for commit in data:
        commit['jira_keys'] = extract_jira_keys(commit.get('message', ''))
    return data
