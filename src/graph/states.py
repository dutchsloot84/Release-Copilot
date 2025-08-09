from typing import List, Dict, Optional
from pydantic import BaseModel


class RunState(BaseModel):
    fix_version: str
    project: str
    repo: str
    branch: str
    since: Optional[str] = None
    jira_issues: List[Dict] = []
    commits: List[Dict] = []
    matches: List[Dict] = []
    missing_in_git: List[Dict] = []
    commits_without_story: List[Dict] = []
    artifacts: Dict[str, str] = {}
    error: Optional[str] = None
