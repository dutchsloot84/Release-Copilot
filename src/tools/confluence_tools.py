from typing import Dict
import requests
from langchain.tools import tool

from src.config.settings import settings
from src.kit.errors import ApiError, ConfigError


@tool
def publish_confluence(title: str, body_markdown: str) -> str:
    """Publish a markdown page to Confluence. Returns page URL."""
    if not settings.confluence_enabled:
        raise ConfigError('Confluence disabled')
    url = f"{settings.confluence_base_url}/rest/api/content"
    data: Dict = {
        'type': 'page',
        'title': title,
        'space': {'key': settings.confluence_space_key},
        'ancestors': [{'id': settings.confluence_parent_page_id}] if settings.confluence_parent_page_id else [],
        'body': {'storage': {'representation': 'wiki', 'value': body_markdown}},
    }
    resp = requests.post(url, json=data, auth=(settings.confluence_email, settings.confluence_api_token), timeout=10)
    if not resp.ok:
        raise ApiError(f"Confluence API error: {resp.status_code}")
    payload = resp.json()
    return payload.get('_links', {}).get('webui', '')
