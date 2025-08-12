from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field('', env='OPENAI_API_KEY')
    openai_planner_model: str = Field('gpt-4o-mini', env='OPENAI_PLANNER_MODEL')
    openai_worker_model: str = Field('gpt-4o-mini', env='OPENAI_WORKER_MODEL')
    openai_writer_model: str = Field('gpt-4o', env='OPENAI_WRITER_MODEL')
    max_tokens_planner: int = Field(1500, env='MAX_TOKENS_PLANNER')
    max_tokens_worker: int = Field(2000, env='MAX_TOKENS_WORKER')
    max_tokens_writer: int = Field(4000, env='MAX_TOKENS_WRITER')

    # Atlassian OAuth 2.0 (3LO)
    ATLASSIAN_OAUTH_CLIENT_ID: str = Field('', env='ATLASSIAN_OAUTH_CLIENT_ID')
    ATLASSIAN_OAUTH_CLIENT_SECRET: str = Field('', env='ATLASSIAN_OAUTH_CLIENT_SECRET')
    JIRA_TOKEN_FILE: str = Field('secrets/jira_oauth.json', env='JIRA_TOKEN_FILE')

    # Jira base (human logs only; API calls use cloudid)
    JIRA_BASE_URL: str = Field('', env='JIRA_BASE_URL')

    # Bitbucket
    bitbucket_base_url: str = Field('', env='BITBUCKET_BASE_URL')
    bitbucket_email: str = Field('', env='BITBUCKET_EMAIL')
    bitbucket_app_password: str = Field('', env='BITBUCKET_APP_PASSWORD')
    bitbucket_project: str = Field('', env='BITBUCKET_PROJECT')

    # Confluence
    confluence_enabled: bool = Field(False, env='CONFLUENCE_ENABLED')
    confluence_base_url: str = Field('', env='CONFLUENCE_BASE_URL')
    confluence_email: str = Field('', env='CONFLUENCE_EMAIL')
    confluence_api_token: str = Field('', env='CONFLUENCE_API_TOKEN')
    confluence_space_key: str = Field('', env='CONFLUENCE_SPACE_KEY')
    confluence_parent_page_id: str = Field('', env='CONFLUENCE_PARENT_PAGE_ID')

    # Toggles
    enable_llamaindex: bool = Field(False, env='ENABLE_LLAMAINDEX')

    DEFAULT_JQL: str | None = Field(None, env='DEFAULT_JQL')
    queries_yaml_path: str = Field('config/queries.yml', env='QUERIES_YAML_PATH')

    @field_validator('confluence_enabled', 'enable_llamaindex', mode='before')
    def _boolify(cls, v):  # type: ignore
        if isinstance(v, bool):
            return v
        return str(v).lower() in {'1', 'true', 'yes', 'on'}


def load_query_presets(path: str | None = None) -> dict[str, str]:
    p = Path(path or settings.queries_yaml_path)
    if not p.exists():
        return {}
    with p.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return (data.get('queries') or {}) if isinstance(data, dict) else {}


settings = Settings()
