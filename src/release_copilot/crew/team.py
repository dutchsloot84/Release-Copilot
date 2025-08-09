"""Placeholder for crew.ai team assembly."""
from typing import List
from release_copilot.kit import registry


def available_tools() -> List[str]:
    return [t.__name__ for t in registry.list_tools()]
