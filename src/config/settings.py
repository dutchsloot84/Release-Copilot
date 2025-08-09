from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = Field('', env='OPENAI_API_KEY')
    openai_planner_model: str = Field('gpt-4o-mini', env='OPENAI_PLANNER_MODEL')
    openai_worker_model: str = Field('gpt-4o-mini', env='OPENAI_WORKER_MODEL')
    openai_writer_model: str = Field('gpt-4o', env='OPENAI_WRITER_MODEL')
    max_tokens_planner: int = Field(1500, env='MAX_TOKENS_PLANNER')
    max_tokens_worker: int = Field(2000, env='MAX_TOKENS_WORKER')
    max_tokens_writer: int = Field(4000, env='MAX_TOKENS_WRITER')

    jira_base_url: str = Field('', env='JIRA_BASE_URL')
    jira_email: str = Field('', env='JIRA_EMAIL')
    jira_api_token: str = Field('', env='JIRA_API_TOKEN')

    bitbucket_base_url: str = Field('', env='BITBUCKET_BASE_URL')
    bitbucket_email: str = Field('', env='BITBUCKET_EMAIL')
    bitbucket_app_password: str = Field('', env='BITBUCKET_APP_PASSWORD')

    confluence_enabled: bool = Field(False, env='CONFLUENCE_ENABLED')
    confluence_base_url: str = Field('', env='CONFLUENCE_BASE_URL')
    confluence_email: str = Field('', env='CONFLUENCE_EMAIL')
    confluence_api_token: str = Field('', env='CONFLUENCE_API_TOKEN')
    confluence_space_key: str = Field('', env='CONFLUENCE_SPACE_KEY')
    confluence_parent_page_id: str = Field('', env='CONFLUENCE_PARENT_PAGE_ID')

    enable_llamaindex: bool = Field(False, env='ENABLE_LLAMAINDEX')

    model_config = {
        'env_file': '.env'
    }

    @field_validator('confluence_enabled', 'enable_llamaindex', mode='before')
    def _boolify(cls, v):  # type: ignore
        if isinstance(v, bool):
            return v
        return str(v).lower() in {'1', 'true', 'yes', 'on'}

settings = Settings()
