#!/usr/bin/env python
"""Generate jira_token.json using OAuth 3LO code exchange."""
from __future__ import annotations
import json, sys, time, requests

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
    data["client_id"] = client_id
    data["client_secret"] = client_secret

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
            data["cloud_id"] = res.get("id")
            data["cloud_url"] = res.get("url")
    except Exception:
        pass

    with open("jira_token.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Token written to jira_token.json")


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
