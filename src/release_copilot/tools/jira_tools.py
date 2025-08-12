from __future__ import annotations
import json
import time
from pathlib import Path
import requests
from typing import List, Dict, Any, Dict as TDict
from release_copilot.kit.caching import load_cache_or_call
from release_copilot.config.settings import Settings

settings = Settings()
TOKEN_PATH = Path("jira_token.json")


def _jira_base_url() -> str:
    base = (settings.jira_base_url or "").rstrip("/")
    try:
        if TOKEN_PATH.exists():
            data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
            url = data.get("cloud_url")
            if url:
                return url.rstrip("/")
            cid = data.get("cloud_id")
            if cid:
                return f"https://api.atlassian.com/ex/jira/{cid}"
    except Exception:
        pass
    if base.lower().endswith("/browse"):
        base = base[: -len("/browse")]
    return base


JIRA = _jira_base_url()
AUTH = (settings.jira_email, settings.jira_api_token)


def _oauth_headers() -> TDict[str, str] | None:
    if not TOKEN_PATH.exists():
        return None
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    access = data.get("access_token")
    expires_at = float(data.get("expires_at", 0))
    if not access:
        return None
    if time.time() >= expires_at - 60:
        refresh = data.get("refresh_token")
        cid = data.get("client_id")
        secret = data.get("client_secret")
        if not (refresh and cid and secret):
            return None
        payload = {
            "grant_type": "refresh_token",
            "client_id": cid,
            "client_secret": secret,
            "refresh_token": refresh,
        }
        r = requests.post("https://auth.atlassian.com/oauth/token", json=payload, timeout=30)
        r.raise_for_status()
        new = r.json()
        access = new.get("access_token")
        data["access_token"] = access
        data["refresh_token"] = new.get("refresh_token", refresh)
        data["expires_at"] = time.time() + int(new.get("expires_in", 3600))
        TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"Authorization": f"Bearer {access}"}


def _auth_kwargs() -> TDict[str, Any]:
    hdrs = _oauth_headers()
    if hdrs:
        return {"headers": hdrs}
    return {"auth": AUTH}

_FIELDS = "key,summary,status,issuetype,assignee,fixVersions,updated"
_MAX_RESULTS = 100


def validate_jql_or_raise(jql: str) -> None:
    """
    Fail fast for malformed JQL with a minimal search.
    Raises requests.HTTPError with the JQL included if status >= 400.
    """
    url = f"{JIRA}/rest/api/2/search"
    params = {"jql": jql, "startAt": 0, "maxResults": 0, "fields": "key"}
    kw = _auth_kwargs()
    r = requests.get(url, params=params, timeout=20, **kw)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        snippet = (jql or "")[:500].replace("\n", " ")
        try:
            details = r.text[:500]
        except Exception:
            details = ""
        raise requests.HTTPError(
            f"JQL validation failed ({r.status_code}). JQL: {snippet}  Details: {details}"
        ) from e


def _search_once(jql: str, start_at: int = 0, max_results: int = _MAX_RESULTS) -> Dict[str, Any]:
    url = f"{JIRA}/rest/api/2/search"
    params = {"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": _FIELDS}
    kw = _auth_kwargs()
    r = requests.get(url, params=params, timeout=30, **kw)
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
