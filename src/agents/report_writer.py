from typing import List, Dict
from pathlib import Path
from pydantic import BaseModel

from src.tools import file_tools


class Report(BaseModel):
    matches: List[Dict]
    missing_in_git: List[Dict]
    commits_without_story: List[Dict]
    summary: str
    artifacts: Dict[str, str]


def compare_jira_and_commits(jira_issues: List[Dict], commits: List[Dict]) -> tuple[List[Dict], List[Dict], List[Dict]]:
    jira_by_key = {j['key']: j for j in jira_issues}
    matches = []
    seen_jira = set()
    commits_without_story = []
    for c in commits:
        if c['jira_keys']:
            for key in c['jira_keys']:
                if key in jira_by_key:
                    matches.append({'key': key, 'summary': jira_by_key[key]['summary'], 'commit': c['id'], 'author': c['author']})
                    seen_jira.add(key)
        else:
            commits_without_story.append({'id': c['id'], 'author': c['author']})
    missing_in_git = [j for k, j in jira_by_key.items() if k not in seen_jira]
    return matches, missing_in_git, commits_without_story


def write_report(jira_issues: List[Dict], commits: List[Dict], output_dir: Path) -> Report:
    matches, missing_in_git, commits_without_story = compare_jira_and_commits(jira_issues, commits)
    summary = (f"{len(matches)} matching issues, {len(missing_in_git)} missing in git, "
               f"{len(commits_without_story)} commits without story")
    excel_path = output_dir / 'release_audit.xlsx'
    md_path = output_dir / 'release_report.md'
    file_tools.write_excel_audit(jira_issues, commits, matches, missing_in_git, commits_without_story, excel_path)
    file_tools.write_markdown_report(summary, md_path)
    return Report(matches=matches, missing_in_git=missing_in_git,
                  commits_without_story=commits_without_story,
                  summary=summary,
                  artifacts={'excel': str(excel_path), 'markdown': str(md_path)})
