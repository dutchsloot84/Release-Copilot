"""Task definitions for crew agents."""
from pydantic import BaseModel


class Task(BaseModel):
    name: str
    description: str
