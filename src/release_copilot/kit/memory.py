from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List

@dataclass
class RunMemory:
    """In-memory store for run events and arbitrary state."""
    state: dict[str, Any] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.events.append(message)
