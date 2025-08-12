from __future__ import annotations
import json, time
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

from release_copilot.config.settings import Settings
from release_copilot.kit.caching import load_cache_or_call

settings = Settings()

AUTH_BASE = "https://auth.atlassian.com"
API_BASE = "https://api.atlassian.com"

TOKEN_FILE = Path(settings.JIRA_TOKEN_FILE)

FIELDS = "key,summary,status,issuetype,assignee,fixVersions,updated"
PAGE_SIZE = 100


class JiraOAuth:
    def __init__(self, client_id: str, client_secret: str, token_path: Path):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_path = token_path
        self._data = self._load()

    def _load(self) -> dict:
        if not self.token_path.exists():
            raise RuntimeError(f"Jira OAuth token file not found: {self.token_path}")
        try:
            return json.loads(self.token_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"Failed to read token file {self.token_path}: {e}")

    def _save(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    @property
    def access_token(self) -> Optional[str]:
        return self._data.get("access_token")

    @property
    def refresh_token(self) -> str:
        rt = self._data.get("refresh_token")
        if not rt:
            raise RuntimeError("refresh_token missing in Jira OAuth token file.")
        return rt

    @property
    def expires_at(self) -> int:
        return int(self._data.get("expires_at") or 0)

    @property
    def cloudid(self) -> Optional[str]:
        return self._data.get("cloudid")

    def _now(self) -> int:
        return int(time.time())

    def _refresh(self) -> None:
        url = f"{AUTH_BASE}/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        self._data["access_token"] = data.get("access_token")
        expires_in = int(data.get("expires_in", 0))
        self._data["expires_at"] = self._now() + max(0, expires_in)
        if data.get("refresh_token"):
            self._data["refresh_token"] = data["refresh_token"]
        self._save()

    def _ensure_access_token(self) -> str:
        if not self.access_token or self._now() >= (self.expires_at - 90):
            self._refresh()
        return self.access_token  # type: ignore

    def _ensure_cloudid(self) -> str:
        if self.cloudid:
            return self.cloudid  # type: ignore
        tok = self._ensure_access_token()
        url = f"{API_BASE}/oauth/token/accessible-resources"
        r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        r.raise_for_status()
        resources = r.json() or []
        if not resources:
            raise RuntimeError("No accessible Jira resources found for this token.")
        for res in resources:
            if res.get("scopes") and "read:jira-work" in res["scopes"]:
                self._data["cloudid"] = res.get("id")
                self._save()
                return self._data["cloudid"]
        self._data["cloudid"] = resources[0].get("id")
        self._save()
        return self._data["cloudid"]

    def session(self) -> requests.Session:
        tok = self._ensure_access_token()
        s = requests.Session()
        s.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {tok}",
        })
        return s

    def base_v3(self) -> str:
        cid = self._ensure_cloudid()
        return f"{API_BASE}/ex/jira/{cid}/rest/api/3"


def validate_jql_or_raise(jql: str) -> None:
    if _oauth is None:
        raise RuntimeError("Jira OAuth not configured")
    s = _oauth.session()
    url = f"{_oauth.base_v3()}/search"
    params = {"jql": jql, "startAt": 0, "maxResults": 0, "fields": "key"}
    r = s.get(url, params=params, timeout=20)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        details = ""
        try:
            details = r.text[:500]
        except Exception:
            pass
        raise requests.HTTPError(
            f"JQL validation failed ({r.status_code}). JQL: {jql}  Details: {details}"
        ) from e


def _search_once(s: requests.Session, jql: str, start_at: int = 0, max_results: int = PAGE_SIZE) -> Dict[str, Any]:
    url = f"{_oauth.base_v3()}/search"
    params = {"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": FIELDS}
    r = s.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def search_issues_cached(jql: str, ttl_hours: int = 12, force_refresh: bool = False) -> List[Dict[str, Any]]:
    if _oauth is None:
        raise RuntimeError("Jira OAuth not configured")
    key = f"jira:search|v3|jql={jql}|fields={FIELDS}"

    def fetch():
        s = _oauth.session()
        data = _search_once(s, jql, start_at=0)
        total = int(data.get("total", 0))
        issues = data.get("issues", [])
        start = len(issues)
        while start < total:
            page = _search_once(s, jql, start_at=start)
            issues.extend(page.get("issues", []))
            start = len(issues)
        out = []
        for i in issues:
            f = i.get("fields", {}) or {}
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

    data, _ = load_cache_or_call(key, ttl_hours=ttl_hours, fetch_fn=fetch, force_refresh=force_refresh)
    return data.get("issues", [])


def get_jira_issues(jql: str | None = None, fix_version: str | None = None) -> List[Dict[str, Any]]:
    """Fetch Jira issues by JQL or fix version label."""
    if not jql:
        if not fix_version:
            raise ValueError("jql or fix_version must be provided")
        jql = f'fixVersion = "{fix_version}"'
    return search_issues_cached(jql)


def _self_test() -> int:
    if _oauth is None:
        print("Jira OAuth self-test failed: OAuth not configured")
        return 1
    try:
        s = _oauth.session()
        cid = _oauth._ensure_cloudid()
        validate_jql_or_raise("ORDER BY updated DESC")
        print(f"Jira OAuth self-test: OK (cloudid={cid})")
        return 0
    except Exception as e:
        print(f"Jira OAuth self-test failed: {e}")
        return 1


try:
    _oauth = JiraOAuth(
        settings.ATLASSIAN_OAUTH_CLIENT_ID,
        settings.ATLASSIAN_OAUTH_CLIENT_SECRET,
        TOKEN_FILE,
    )
except Exception:
    _oauth = None

if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("Usage: python -m release_copilot.tools.jira_tools --self-test")
