from typing import Callable, List

_TOOLS: List[Callable] = []


def register(tool: Callable) -> None:
    """Register a tool for use by crew agents."""
    _TOOLS.append(tool)


def list_tools() -> List[Callable]:
    return list(_TOOLS)
