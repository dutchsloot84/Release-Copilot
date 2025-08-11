import re
from datetime import datetime
from typing import Dict, List, Optional

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
    base = settings.bitbucket_base_url.rstrip("/")
    url = f"{base}/projects/{project}/repos/{repo}/commits"
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


def fetch_commits_window(
    project: str,
    repo: str,
    branch: str,
    since_utc: datetime,
    until_utc: datetime,
) -> List[Dict]:
    """Paginate commits (newest first) and filter by ``authorTimestamp``.

    Parameters
    ----------
    project, repo, branch:
        Bitbucket identifiers.
    since_utc, until_utc:
        Inclusive UTC datetime window.
    """

    base = settings.bitbucket_base_url.rstrip("/")
    url = f"{base}/projects/{project}/repos/{repo}/commits"
    start = 0
    commits: List[Dict] = []
    since_ms = int(since_utc.timestamp() * 1000)
    until_ms = int(until_utc.timestamp() * 1000)

    while True:
        params = {"until": branch, "start": start, "limit": 100}
        resp = requests.get(
            url,
            params=params,
            auth=(settings.bitbucket_email, settings.bitbucket_app_password),
            timeout=10,
        )
        if not resp.ok:
            raise ApiError(f"Bitbucket API error: {resp.status_code}")

        payload = resp.json()
        values = payload.get("values", [])
        stop = False
        for commit in values:
            ts = commit.get("authorTimestamp", 0)
            if ts < since_ms:
                stop = True
                break
            if since_ms <= ts <= until_ms:
                commit["jira_keys"] = extract_jira_keys(commit.get("message", ""))
                commit["message"] = (commit.get("message", "") or "")[:1000]
                commits.append(commit)

        if stop or payload.get("isLastPage"):
            break
        start = payload.get("nextPageStart")

    return commits
