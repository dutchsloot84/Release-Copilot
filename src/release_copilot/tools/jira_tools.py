from typing import List
import requests
from langchain.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from release_copilot.config.settings import settings
from release_copilot.kit.caching import cache_json

BASE = settings.jira_base_url
AUTH = (settings.jira_email, settings.jira_api_token)


def _resolve_jql(user_jql: str | None, fix_version: str | None) -> str:
    if user_jql and user_jql.strip():
        return user_jql.strip()
    tmpl = (settings.default_jql or '').strip()
    if tmpl:
        if '{fix_version}' in tmpl and not fix_version:
            raise ValueError('DEFAULT_JQL requires {fix_version}, but fix_version is missing.')
        return tmpl.format(fix_version=fix_version) if '{fix_version}' in tmpl else tmpl
    if fix_version:
        return f'fixVersion = "{fix_version}" ORDER BY key'
    raise ValueError('No JQL provided and no fix_version available to build a default query.')


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def _jira_search(jql: str, start_at: int = 0, max_results: int = 50, fields: str = 'key,summary,status'):
    params = {
        'jql': jql,
        'startAt': start_at,
        'maxResults': max_results,
        'fields': fields,
    }
    r = requests.get(f'{BASE}/rest/api/2/search', params=params, auth=AUTH, timeout=10)
    r.raise_for_status()
    return r.json()


@cache_json('jira', ttl_hours=12)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def _fetch_jira_issues(jql: str) -> List[dict]:
    issues: List[dict] = []
    start = 0
    page_size = 200
    while True:
        data = _jira_search(jql + ' ORDER BY key', start_at=start, max_results=page_size)
        page = data.get('issues', [])
        issues.extend([
            {
                'key': i['key'],
                'summary': i['fields']['summary'],
                'status': i['fields']['status']['name'],
            }
            for i in page
        ])
        if len(page) < page_size:
            break
        start += page_size
    return issues


@tool('get_jira_issues', return_direct=False)
def get_jira_issues(jql: str | None = None, fix_version: str | None = None) -> List[dict]:
    """Return issues (key, summary, status) using provided JQL or a default built from fix_version."""
    final_jql = _resolve_jql(jql, fix_version)
    _jira_search(final_jql, max_results=1)  # validate
    return _fetch_jira_issues(final_jql)
