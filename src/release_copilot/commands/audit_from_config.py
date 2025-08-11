from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from release_copilot.config.settings import settings  # noqa: F401 - ensure .env loading
from release_copilot.kit.caching import CacheKey, load_cache_or_call
from release_copilot.reporting.llm_summary import build_llm_summary
from release_copilot.tools.bitbucket_tools import fetch_commits_window
from release_copilot.tools.config_loader import ConfigData, load_config


def _parse_iso_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _default_window() -> Tuple[datetime, datetime]:
    until = datetime.now(tz=timezone.utc)
    since = until - timedelta(weeks=4)
    return since, until


def _branch_loop(args, cfg: ConfigData) -> List[str]:
    """Resolve branches based on config and CLI flags, logging decisions."""

    develop_branch = args.develop_branch or cfg.develop_branch
    release_branch = args.release_branch or cfg.release_branch

    branches: List[str] = []
    if args.develop_only:
        if not develop_branch:
            raise SystemExit("Develop branch not defined")
        print("Flag --develop-only: release branch skipped")
        branches.append(develop_branch)
    elif args.release_only:
        if not release_branch:
            raise SystemExit("Release branch not defined")
        print("Flag --release-only: develop branch skipped")
        branches.append(release_branch)
    else:
        if release_branch:
            branches.append(release_branch)
        else:
            print("Release branch not defined; skipping")
        if develop_branch:
            branches.append(develop_branch)
        else:
            print("Develop branch not defined; skipping")

    print(f"Branches resolved: {', '.join(branches)}")
    return branches


def _write_commits_csv(path: Path, commits: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "displayId",
        "author",
        "authorTimestamp",
        "message",
        "jira_keys",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in commits:
            writer.writerow(
                {
                    "id": c.get("id"),
                    "displayId": c.get("displayId"),
                    "author": (c.get("author", {}) or {}).get("name"),
                    "authorTimestamp": c.get("authorTimestamp"),
                    "message": (c.get("message", "") or "")[:1000],
                    "jira_keys": ",".join(c.get("jira_keys", [])),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--develop-branch")
    parser.add_argument("--release-branch")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--develop-only", action="store_true")
    group.add_argument("--release-only", action="store_true")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--cache-ttl-hours", type=int, default=12)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--output-dir", default="data/outputs")
    parser.add_argument("--write-llm-summary", action="store_true", default=False, help="Generate optional LLM-written narrative")
    parser.add_argument("--llm-model", type=str, default="gpt-4o-mini", help="LLM model for narrative (default: gpt-4o-mini)")
    parser.add_argument("--llm-max-tokens", type=int, default=1200, help="Max tokens for LLM completion")
    parser.add_argument("--llm-budget-cents", type=int, default=10, help="Hard cap on estimated LLM spend (cents)")
    parser.add_argument("--llm-top-n", type=int, default=15, help="Highlights per repo to include in LLM context")
    parser.add_argument("--llm-report-name", type=str, default="release_audit_llm", help="Base name for LLM markdown")
    args = parser.parse_args()

    cfg = load_config(args.config)

    since_utc, until_utc = (
        (_parse_iso_date(args.since), _parse_iso_date(args.until))
        if args.since and args.until
        else _default_window()
    )

    branches = _branch_loop(args, cfg)
    print(f"Commit window: {since_utc.isoformat()} to {until_utc.isoformat()}")

    repo_pairs = []
    for key in cfg.repos:
        if "/" not in key:
            raise SystemExit(f"Invalid repo format '{key}', expected PROJECT/REPO")
        repo_pairs.append(tuple(key.split("/", 1)))
    print(f"Repos: {', '.join([f'{p}/{r}' for p,r in repo_pairs])}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: List[dict] = []
    repo_csv_map: Dict[str, Path] = {}

    for project, repo in repo_pairs:
        for branch in branches:
            key = str(
                CacheKey(
                    "bb:commits",
                    {
                        "project": project,
                        "repo": repo,
                        "branch": branch,
                        "since": since_utc.isoformat(),
                        "until": until_utc.isoformat(),
                    },
                )
            )

            def fetch() -> List[dict]:
                return fetch_commits_window(project, repo, branch, since_utc, until_utc)

            commits, source = load_cache_or_call(
                key,
                ttl_hours=args.cache_ttl_hours,
                fetch_fn=fetch,
                force_refresh=args.force_refresh,
            )

            print(f"{project}/{repo} {branch}: {source} ({len(commits)} commits)")

            branch_safe = branch.replace("/", "_")
            csv_name = f"commits_{project}_{repo}_{branch_safe}_{since_utc:%Y%m%d}_{until_utc:%Y%m%d}.csv"
            csv_path = output_dir / csv_name
            _write_commits_csv(csv_path, commits)
            repo_csv_map[repo] = csv_path

            summary_rows.append(
                {
                    "project": project,
                    "repo": repo,
                    "branch": branch,
                    "count": len(commits),
                    "since_iso": since_utc.isoformat(),
                    "until_iso": until_utc.isoformat(),
                    "csv_path": str(csv_path),
                    "source": source,
                }
            )

    summary_path = output_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "project",
                "repo",
                "branch",
                "count",
                "since_iso",
                "until_iso",
                "csv_path",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Summary written to {summary_path}")

    branches_label = ", ".join(branches)
    if args.write_llm_summary:
        try:
            llm_md = build_llm_summary(
                summary_rows=summary_rows,
                output_dir=output_dir,
                window=(since_utc, until_utc),
                branches_label=branches_label,
                repo_csv_map=repo_csv_map,
                model=args.llm_model,
                max_tokens=args.llm_max_tokens,
                budget_cents=args.llm_budget_cents,
                top_n_per_repo=args.llm_top_n,
                base_name=args.llm_report_name,
                fix_version=getattr(args, "fix_version", None) if hasattr(args, "fix_version") else None,
            )
            print(f"LLM summary written: {llm_md}")
        except Exception as e:
            print(f"LLM summary skipped: {e}")
    else:
        print("LLM summary not requested (use --write-llm-summary to enable).")


if __name__ == "__main__":
    main()
