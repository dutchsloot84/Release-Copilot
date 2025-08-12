from __future__ import annotations
from dataclasses import dataclass
from typing import List
from rich.console import Console

# Rough price mapping per 1K tokens
MODEL_PRICES = {
    'gpt-4o-mini': {'prompt': 0.00015, 'completion': 0.0006},
    'gpt-4o': {'prompt': 0.005, 'completion': 0.015},
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
        price = MODEL_PRICES.get(self.model, {'prompt': 0.0, 'completion': 0.0})
        return (
            self.prompt_tokens * price.get('prompt', 0.0)
            + self.completion_tokens * price.get('completion', 0.0)
        ) / 1000


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
