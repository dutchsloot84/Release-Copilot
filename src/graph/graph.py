from pathlib import Path
from src.graph.states import RunState
from src.agents import planner, jira_analyst, git_historian, report_writer, publisher


def compile_graph():
    def run(state: RunState) -> RunState:
        plan = planner.plan_run(state.fix_version, state.project, state.repo, state.branch)
        if 'collect_jira' in plan.steps:
            state.jira_issues = jira_analyst.collect_jira(state.jql, state.fix_version).issues
        if 'collect_commits' in plan.steps:
            state.commits = git_historian.collect_commits(state.project, state.repo, state.branch, state.since).commits
        if 'compare' in plan.steps:
            matches, missing, orphan_commits = report_writer.compare_jira_and_commits(state.jira_issues, state.commits)
            state.matches = matches
            state.missing_in_git = missing
            state.commits_without_story = orphan_commits
        if 'write_report' in plan.steps:
            report = report_writer.write_report(state.jira_issues, state.commits, Path('data/outputs'))
            state.artifacts = report.artifacts
        if publisher and state.artifacts.get('markdown') and False:  # publishing disabled by default
            publisher.publish(Path(state.artifacts['markdown']))
        return state

    return run
