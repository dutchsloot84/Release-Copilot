from __future__ import annotations
import requests
from typing import List, Dict, Any
from release_copilot.kit.caching import load_cache_or_call
from release_copilot.config.settings import Settings

settings = Settings()
JIRA = (settings.jira_base_url or "").rstrip("/")
if JIRA.lower().endswith("/browse"):
    JIRA = JIRA[: -len("/browse")]
AUTH = (settings.jira_email, settings.jira_api_token)

_FIELDS = "key,summary,status,issuetype,assignee,fixVersions,updated"
_MAX_RESULTS = 100


def _search_once(jql: str, start_at: int = 0, max_results: int = _MAX_RESULTS) -> Dict[str, Any]:
    url = f"{JIRA}/rest/api/2/search"
    params = {"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": _FIELDS}
    r = requests.get(url, params=params, auth=AUTH, timeout=30)
    r.raise_for_status()
    return r.json()


def search_issues_cached(jql: str, ttl_hours: int = 12, force_refresh: bool = False) -> List[Dict[str, Any]]:
    key = f"jira:search|jql={jql}|fields={_FIELDS}"

    def fetch():
        data = _search_once(jql, start_at=0)
        total = int(data.get("total", 0))
        issues = data.get("issues", [])
        start = _MAX_RESULTS
        while len(issues) < total:
            page = _search_once(jql, start_at=start)
            issues.extend(page.get("issues", []))
            start += _MAX_RESULTS
        out = []
        for i in issues:
            f = i.get("fields", {})
            out.append({
                "key": i.get("key"),
                "summary": f.get("summary"),
                "status": (f.get("status") or {}).get("name"),
                "issuetype": (f.get("issuetype") or {}).get("name"),
                "assignee": ((f.get("assignee") or {}).get("displayName") or ""),
                "fixVersions": [v.get("name") for v in (f.get("fixVersions") or [])],
                "updated": f.get("updated"),
                "self": i.get("self"),
            })
        return {"issues": out}

    data, source = load_cache_or_call(key, ttl_hours=ttl_hours, fetch_fn=fetch, force_refresh=force_refresh)
    return data.get("issues", [])
