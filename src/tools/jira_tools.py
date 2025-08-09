from typing import List, Dict
import requests
from langchain.tools import tool
from tenacity import retry, wait_fixed, stop_after_attempt

from src.config.settings import settings
from src.kit.caching import cache_json
from src.kit.errors import ApiError


@tool
def get_jira_issues_for_fixversion(fix_version: str) -> List[Dict]:
    """Fetch Jira issues for a given fix version."""
    return _get_jira_issues_for_fixversion(fix_version)


@cache_json('jira', ttl_hours=12)
@retry(wait_fixed(2), stop=stop_after_attempt(3))
def _get_jira_issues_for_fixversion(fix_version: str) -> List[Dict]:
    url = f"{settings.jira_base_url}/rest/api/2/search"
    jql = f"fixVersion={fix_version}"
    resp = requests.get(url, params={'jql': jql}, auth=(settings.jira_email, settings.jira_api_token), timeout=10)
    if not resp.ok:
        raise ApiError(f"Jira API error: {resp.status_code}")
    data = resp.json()
    return data.get('issues', [])
