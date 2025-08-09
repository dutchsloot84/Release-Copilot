from __future__ import annotations
from dataclasses import dataclass
from typing import List
from rich.console import Console

# Rough price mapping per 1K tokens
MODEL_PRICES = {
    'gpt-4o-mini': 0.00015,
    'gpt-4o': 0.01,
}

console = Console()

@dataclass
class StepCost:
    name: str
    prompt_tokens: int
    completion_tokens: int
    model: str

    @property
    def cost(self) -> float:
        price = MODEL_PRICES.get(self.model, 0.0)
        return price * (self.prompt_tokens + self.completion_tokens) / 1000


class CostSession:
    def __init__(self) -> None:
        self.steps: List[StepCost] = []

    def record(self, name: str, prompt_tokens: int, completion_tokens: int, model: str) -> None:
        self.steps.append(StepCost(name, prompt_tokens, completion_tokens, model))

    def __enter__(self) -> 'CostSession':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        total = sum(s.cost for s in self.steps)
        console.print('\n[bold]Cost summary[/bold]')
        for s in self.steps:
            console.print(f"{s.name}: {s.prompt_tokens}/{s.completion_tokens} tokens -> ${s.cost:.4f}")
        console.print(f"Total: ${total:.4f}")
