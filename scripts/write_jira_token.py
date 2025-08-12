#!/usr/bin/env python
"""Generate Jira OAuth token file using OAuth 3LO code exchange."""
from __future__ import annotations
import json, os, sys, time, requests
from pathlib import Path

USAGE = "Usage: python write_jira_token.py CLIENT_ID CLIENT_SECRET CODE [--redirect-uri URI]"


def main(client_id: str, client_secret: str, code: str, redirect_uri: str) -> None:
    url = "https://auth.atlassian.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    data["expires_at"] = time.time() + int(data.get("expires_in", 3600))

    # Try to capture cloud information for easier API calls
    try:
        r2 = requests.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {data.get('access_token')}"},
            timeout=30,
        )
        r2.raise_for_status()
        resources = r2.json()
        if resources:
            res = resources[0]
            data["cloudid"] = res.get("id")
    except Exception:
        pass

    token_path = Path(os.getenv("JIRA_TOKEN_FILE", "secrets/jira_oauth.json"))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with token_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Token written to {token_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(USAGE)
        sys.exit(1)
    client_id, client_secret, code = sys.argv[1:4]
    redirect_uri = "http://localhost:8080/callback"
    if len(sys.argv) > 4:
        if sys.argv[4] == "--redirect-uri" and len(sys.argv) > 5:
            redirect_uri = sys.argv[5]
    main(client_id, client_secret, code, redirect_uri)
