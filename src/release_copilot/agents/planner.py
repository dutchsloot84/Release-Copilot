from pydantic import BaseModel

class Plan(BaseModel):
    steps: list[str]


def plan_run(fix_version: str, project: str, repo: str, branch: str) -> Plan:
    """Very small planner returning the sequence of tasks."""
    return Plan(steps=['collect_jira', 'collect_commits', 'compare', 'write_report'])
