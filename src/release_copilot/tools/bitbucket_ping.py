from __future__ import annotations
import requests
from typing import Tuple
from release_copilot.config.settings import Settings

def bitbucket_ping(project_key: str) -> Tuple[bool, str]:
    """
    Lightweight connectivity check against Bitbucket Server/DC:
    - GET /rest/api/1.0/projects/{project}/repos?limit=1
    Returns (ok, message).
    """
    s = Settings()
    base = s.bitbucket_base_url.rstrip("/")
    email = s.bitbucket_email
    token = s.bitbucket_app_password
    try:
        url = f"{base}/projects/{project_key}/repos"
        r = requests.get(url, params={"limit": 1}, auth=(email, token), timeout=15)
        if r.status_code in (401, 403):
            return False, f"Bitbucket auth failed ({r.status_code})."
        r.raise_for_status()
        return True, "Bitbucket OK"
    except Exception as e:
        return False, f"Bitbucket error: {e}"
