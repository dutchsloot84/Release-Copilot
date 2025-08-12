from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class RunState(BaseModel):
    fix_version: str
    project: str
    repo: str
    branch: str
    since: Optional[str] = None
    jql: Optional[str] = None
    jira_issues: List[Dict] = Field(default_factory=list)
    commits: List[Dict] = Field(default_factory=list)
    matches: List[Dict] = Field(default_factory=list)
    missing_in_git: List[Dict] = Field(default_factory=list)
    commits_without_story: List[Dict] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None
