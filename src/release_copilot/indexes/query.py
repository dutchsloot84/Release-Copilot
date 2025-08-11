from typing import List

from release_copilot.config.settings import settings


def query_knowledge(prompt: str) -> List[str]:
    """Return up to 3 snippets relevant to the prompt."""
    if not settings.enable_llamaindex:
        return []
    # A real implementation would query the index; here we return empty.
    return []
