from pathlib import Path
from pydantic import BaseModel

from src.config.settings import settings
from src.tools.confluence_tools import publish_confluence


class PublishResult(BaseModel):
    url: str | None


def publish(summary_path: Path) -> PublishResult:
    if not settings.confluence_enabled:
        return PublishResult(url=None)
    url = publish_confluence('Release Report', summary_path.read_text())
    return PublishResult(url=url)
