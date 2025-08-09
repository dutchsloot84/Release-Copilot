import os
from getpass import getpass
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.prompt import Prompt, Confirm
from dotenv import dotenv_values, set_key

console = Console()

ENV_PATH = Path('.') / '.env'


def _test_endpoint(url: str, auth: Optional[tuple[str, str]] = None) -> bool:
    try:
        resp = requests.get(url, auth=auth, timeout=5)
        return resp.ok
    except Exception:
        return False


def run_wizard() -> None:
    console.print('[bold]Release Copilot Environment Wizard[/bold]')
    data = {}
    data['JIRA_BASE_URL'] = Prompt.ask('Jira base URL (e.g. https://jira.example.com)').rstrip('/')
    data['JIRA_EMAIL'] = Prompt.ask('Jira email')
    data['JIRA_API_TOKEN'] = getpass('Jira API token: ')

    jira_ok = _test_endpoint(f"{data['JIRA_BASE_URL']}/rest/api/2/myself", auth=(data['JIRA_EMAIL'], data['JIRA_API_TOKEN']))
    console.print(f"Jira connectivity: {'[green]✓[/green]' if jira_ok else '[red]✗[/red]'}")

    data['BITBUCKET_BASE_URL'] = Prompt.ask('Bitbucket base URL (e.g. https://bitbucket.example.com)').rstrip('/')
    data['BITBUCKET_EMAIL'] = Prompt.ask('Bitbucket email')
    data['BITBUCKET_APP_PASSWORD'] = getpass('Bitbucket app password: ')

    bb_ok = _test_endpoint(f"{data['BITBUCKET_BASE_URL']}/rest/api/1.0/projects", auth=(data['BITBUCKET_EMAIL'], data['BITBUCKET_APP_PASSWORD']))
    console.print(f"Bitbucket connectivity: {'[green]✓[/green]' if bb_ok else '[red]✗[/red]'}")

    enable_conf = Confirm.ask('Enable Confluence publishing?', default=False)
    data['CONFLUENCE_ENABLED'] = str(enable_conf).lower()
    if enable_conf:
        data['CONFLUENCE_BASE_URL'] = Prompt.ask('Confluence base URL').rstrip('/')
        data['CONFLUENCE_EMAIL'] = Prompt.ask('Confluence email')
        data['CONFLUENCE_API_TOKEN'] = getpass('Confluence API token: ')
        data['CONFLUENCE_SPACE_KEY'] = Prompt.ask('Confluence space key')
        data['CONFLUENCE_PARENT_PAGE_ID'] = Prompt.ask('Confluence parent page id')
    else:
        data['CONFLUENCE_BASE_URL'] = ''
        data['CONFLUENCE_EMAIL'] = ''
        data['CONFLUENCE_API_TOKEN'] = ''
        data['CONFLUENCE_SPACE_KEY'] = ''
        data['CONFLUENCE_PARENT_PAGE_ID'] = ''

    enable_index = Confirm.ask('Enable LlamaIndex for knowledge snippets?', default=False)
    data['ENABLE_LLAMAINDEX'] = str(enable_index).lower()

    # load defaults from env.example
    defaults = dotenv_values('.env.example')
    for key, val in defaults.items():
        if key not in data:
            data[key] = val

    console.print(f"Writing environment to {ENV_PATH}")
    for key, value in data.items():
        set_key(ENV_PATH, key, value)

    console.print('[green]Done.[/green] You can rerun the wizard anytime.')


if __name__ == '__main__':
    run_wizard()
