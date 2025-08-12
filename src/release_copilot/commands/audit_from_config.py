from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from release_copilot.config.settings import settings
from release_copilot.kit.caching import CacheKey, load_cache_or_call
from release_copilot.kit.jira_key import extract_keys
from release_copilot.reporting.llm_summary import build_llm_summary
from release_copilot.reporting.report_builder import build_reports
from release_copilot.tools.bitbucket_tools import fetch_commits_window
from release_copilot.tools.config_loader import ConfigData, load_config
from release_copilot.tools.jira_tools import search_issues_cached, validate_jql_or_raise

logger = logging.getLogger(__name__)


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


def _write_commits_csv(path: Path, commits: Iterable[dict], project: str, repo: str, branch: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "project",
        "repo",
        "branch",
        "id",
        "displayId",
        "author",
        "authorEmail",
        "authorTimestamp",
        "message",
        "jira_keys",
        "link",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in commits:
            author = c.get("author", {}) or {}
            link = ""
            links = (c.get("links") or {}).get("self")
            if isinstance(links, list) and links:
                link = links[0].get("href", "")
            writer.writerow(
                {
                    "project": project,
                    "repo": repo,
                    "branch": branch,
                    "id": c.get("id"),
                    "displayId": c.get("displayId"),
                    "author": author.get("name"),
                    "authorEmail": author.get("emailAddress"),
                    "authorTimestamp": c.get("authorTimestamp"),
                    "message": (c.get("message", "") or "")[:1000],
                    "jira_keys": ",".join(c.get("jira_keys", [])),
                    "link": link,
                }
            )


def _write_csv(path: Path, fieldnames: List[str], rows: List[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    return path


def _clean_fix_version(raw: Optional[str]) -> Optional[str]:
    """
    Clean user-supplied Fix Version safely:
    - Trim outer whitespace
    - Remove wrapping single/double quotes if present
    - Keep internal spacing exactly as typed
    """
    if not raw:
        return None
    v = raw.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        v = v[1:-1].strip()
    return v


def resolve_jql(args, settings) -> str:
    """
    Resolve the final JQL string:
    - If --jql is provided, return it trimmed.
    - Else use settings.DEFAULT_JQL verbatim (no edits), substituting {fix_version} if present.
    - If template needs {fix_version} but it's missing, exit with a clear message.
    """
    if getattr(args, "jql", None):
        return args.jql.strip()

    tmpl = settings.DEFAULT_JQL  # DO NOT modify/strip
    if not tmpl:
        raise SystemExit("No JQL provided and DEFAULT_JQL is empty. Provide --jql or set DEFAULT_JQL in .env")

    if "{fix_version}" in tmpl:
        fv = _clean_fix_version(getattr(args, "fix_version", None))
        if not fv:
            raise SystemExit("DEFAULT_JQL requires {fix_version}. Provide --fix-version.")
        return tmpl.format(fix_version=fv)

    return tmpl

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
    parser.add_argument("--write-report", action="store_true", help="Write Markdown and Excel reports")
    parser.add_argument("--report-name", type=str, default="release_audit", help="Base name for Markdown/Excel reports")
    parser.add_argument("--write-llm-summary", action="store_true", default=False, help="Generate optional LLM-written narrative")
    parser.add_argument("--llm-model", type=str, default=None, help="LLM model for narrative (default from config or gpt-4o-mini)")
    parser.add_argument("--llm-max-tokens", type=int, default=1200, help="Max tokens for LLM completion")
    parser.add_argument("--llm-budget-cents", type=int, default=10, help="Hard cap on estimated LLM spend (cents)")
    parser.add_argument("--llm-top-n", type=int, default=15, help="Highlights per repo to include in LLM context")
    parser.add_argument("--llm-report-name", type=str, default="release_audit_llm", help="Base name for LLM markdown")
    parser.add_argument("--fix-version", type=str, default=None, help='Fix Version label or date (e.g. "Mobilitas 2025.08.22") for JQL substitution')
    parser.add_argument("--jql", type=str, default=None, help="Custom JQL (overrides default)")
    parser.add_argument("--jql-ttl-hours", type=int, default=12, help="Cache TTL for Jira search")
    parser.add_argument("--jql-force-refresh", action="store_true", help="Bypass Jira cache")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if not args.fix_version and cfg.fix_version:
        args.fix_version = cfg.fix_version
    if not args.llm_model:
        args.llm_model = cfg.llm_model or "gpt-4o-mini"

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
            _write_commits_csv(csv_path, commits, project, repo, branch)
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

    # Jira comparison
    missing_rows: List[dict] = []
    orphan_commit_rows: List[dict] = []
    try:
        jql = resolve_jql(args, settings)
        logger.info("Resolved JQL: %s", jql)
        validate_jql_or_raise(jql)
        jira_issues = search_issues_cached(jql, ttl_hours=args.jql_ttl_hours, force_refresh=args.jql_force_refresh)
        jira_keys = {i["key"] for i in jira_issues}

        commit_rows: List[dict] = []
        for sr in summary_rows:
            csv_path = Path(sr["csv_path"])
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    msg = r.get("message", "")
                    keys = extract_keys(msg)
                    r["_extracted_keys"] = ";".join(keys)
                    r["_keys_set"] = set(keys)
                    commit_rows.append(r)

        commit_keys = set().union(*(r["_keys_set"] for r in commit_rows)) if commit_rows else set()
        missing_keys = sorted(list(jira_keys - commit_keys))
        issue_by_key = {i["key"]: i for i in jira_issues}
        for k in missing_keys:
            i = issue_by_key.get(k, {})
            missing_rows.append({
                "key": k,
                "summary": i.get("summary", ""),
                "status": i.get("status", ""),
                "assignee": i.get("assignee", ""),
                "fixVersions": ", ".join(i.get("fixVersions", []) or []),
                "updated": i.get("updated", ""),
            })

        orphan_commit_rows = [r for r in commit_rows if len(r["_keys_set"]) == 0 or not (r["_keys_set"] & jira_keys)]

        missing_csv = output_dir / "missing_in_repo.csv"
        orphan_csv = output_dir / "orphan_commits.csv"
        _write_csv(missing_csv, ["key", "summary", "status", "assignee", "fixVersions", "updated"], missing_rows)
        _write_csv(
            orphan_csv,
            [
                "project",
                "repo",
                "branch",
                "displayId",
                "author",
                "authorEmail",
                "authorTimestamp",
                "message",
                "link",
                "extracted_keys",
            ],
            [
                {
                    "project": r.get("project", ""),
                    "repo": r.get("repo", ""),
                    "branch": r.get("branch", ""),
                    "displayId": r.get("displayId") or (r.get("id", "")[:10]),
                    "author": r.get("author", ""),
                    "authorEmail": r.get("authorEmail", ""),
                    "authorTimestamp": r.get("authorTimestamp", ""),
                    "message": r.get("message", ""),
                    "link": r.get("link", ""),
                    "extracted_keys": r.get("_extracted_keys", ""),
                }
                for r in orphan_commit_rows
            ],
        )
        print(f"Missing-in-repo: {len(missing_rows)} | Orphan commits: {len(orphan_commit_rows)}")
    except Exception as e:
        logger.warning("Jira comparison skipped: %s", e)
        missing_rows = []
        orphan_commit_rows = []

    branches_label = ", ".join(branches)
    if args.write_report:
        build_reports(summary_rows, output_dir, repo_csv_map, base_name=args.report_name)

    if args.write_llm_summary:
        missing_preview = missing_rows[:20]
        orphan_preview = [
            {
                "repo": r.get("repo", ""),
                "displayId": r.get("displayId", ""),
                "line": (r.get("message", "") or "").splitlines()[0][:160],
            }
            for r in orphan_commit_rows[:20]
        ]
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
                fix_version=_clean_fix_version(getattr(args, "fix_version", None)) if hasattr(args, "fix_version") else None,
                missing_preview=missing_preview,
                orphan_preview=orphan_preview,
            )
            print(f"LLM summary written: {llm_md}")
        except Exception as e:
            print(f"LLM summary skipped: {e}")
    else:
        print("LLM summary not requested (use --write-llm-summary to enable).")


if __name__ == "__main__":
    main()
