import argparse
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any

from rich.console import Console
from rich.progress import Progress

from src.config import env_wizard
from src.graph.states import RunState
from src.graph.graph import compile_graph
from src.kit.cost_meter import CostSession

LOG_PATH = Path('logs/release-copilot.log')
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=5)
logging.getLogger().addHandler(handler)

console = Console()


def run_release_audit(
    fix_version: str,
    project: str,
    repo: str,
    branch: str,
    since: Optional[str] = None,
    jql: Optional[str] = None,
    enable_confluence: bool = False,
    enable_llamaindex: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run the pipeline and return a result dict."""
    result: Dict[str, Any] = {
        "artifacts": {},
        "counts": {},
        "cost": {},
        "log_path": str(LOG_PATH),
        "ok": False,
        "error": None,
    }
    try:
        os.environ["CONFLUENCE_ENABLED"] = str(enable_confluence).lower()
        os.environ["ENABLE_LLAMAINDEX"] = str(enable_llamaindex).lower()
        os.environ["DRY_RUN"] = str(dry_run).lower()

        state = RunState(
            fix_version=fix_version,
            project=project,
            repo=repo,
            branch=branch,
            since=since,
            jql=jql,
        )

        graph = compile_graph()

        with CostSession() as cost:
            with Progress() as progress:
                task = progress.add_task('Running', total=1)
                graph(state)
                progress.update(task, advance=1)

        artifacts = state.artifacts
        counts = {
            "jira_total": len(state.jira_issues),
            "commits_total": len(state.commits),
            "missing_in_git": len(state.missing_in_git),
            "commits_without_story": len(state.commits_without_story),
        }
        tokens = {
            s.name: {
                "prompt": s.prompt_tokens,
                "completion": s.completion_tokens,
                "model": s.model,
            }
            for s in cost.steps
        }
        cost_total = sum(s.cost for s in cost.steps)

        result.update(
            {
                "artifacts": artifacts,
                "counts": counts,
                "cost": {"tokens_by_step": tokens, "estimated_usd": cost_total},
                "ok": True,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        result["error"] = str(exc)

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--wizard', action='store_true')
    parser.add_argument('--fix-version')
    parser.add_argument('--project')
    parser.add_argument('--repo')
    parser.add_argument('--branch')
    parser.add_argument('--since')
    parser.add_argument('--enable-confluence', action='store_true')
    parser.add_argument('--enable-llamaindex', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--jql', type=str, default=None, help='Custom JQL to run (overrides defaults).')
    parser.add_argument('--jql-preset', type=str, default=None, help='Name of a JQL preset from config/queries.yml')
    args = parser.parse_args()

    if args.wizard:
        env_wizard.run_wizard()
        return

    from src.config.settings import load_query_presets

    presets = load_query_presets()
    effective_jql = None
    if args.jql:
        effective_jql = args.jql
    elif args.jql_preset:
        if args.jql_preset not in presets:
            raise SystemExit(f"Unknown JQL preset '{args.jql_preset}'. Available: {', '.join(presets.keys()) or '(none)'}")
        tmpl = presets[args.jql_preset]
        effective_jql = tmpl.format(fix_version=args.fix_version) if "{fix_version}" in tmpl else tmpl

    res = run_release_audit(
        fix_version=args.fix_version,
        project=args.project,
        repo=args.repo,
        branch=args.branch,
        since=args.since,
        jql=effective_jql,
        enable_confluence=args.enable_confluence,
        enable_llamaindex=args.enable_llamaindex,
        dry_run=args.dry_run,
    )

    if not res.get("ok"):
        console.print(f"[red]Run failed: {res.get('error')}[/red]")
        raise SystemExit(1)

    console.print('Artifacts:')
    for name, path in res["artifacts"].items():
        console.print(f" - {name}: {path}")

    console.print('Run complete.')


if __name__ == '__main__':
    main()
