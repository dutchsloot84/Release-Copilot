from __future__ import annotations

import csv
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from release_copilot.kit.caching import load_cache_or_call  # existing helper
from release_copilot.config.settings import Settings  # loads .env (no OS env reads)

# ------------------ CSV utilities ------------------

def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def _first_line(msg: str) -> str:
    return (msg or "").splitlines()[0].strip()

def _score_commit(msg: str) -> int:
    """Very light heuristic: favor feat/fix/refactor and JIRA keys-like tokens."""
    m = msg.lower()
    score = 0
    if "feat" in m: score += 3
    if "fix" in m: score += 3
    if "refactor" in m: score += 2
    if "perf" in m or "perf:" in m: score += 2
    if "bug" in m: score += 2
    # crude JIRA key hint
    for token in ["-", "_"]:
        if token in msg and any(ch.isalpha() for ch in msg.split(token)[0]):
            score += 1
            break
    return score

def _truncate(s: str, limit: int = 160) -> str:
    s = s.strip()
    return s if len(s) <= limit else s[:limit - 1] + "…"

def select_highlights(csv_path: Path, top_n: int = 15) -> List[Dict[str, str]]:
    rows = _read_csv_rows(csv_path)
    # De-dup by approximate jiraish key if present in message, else by displayId
    seen_keys: set[str] = set()
    scored: List[Tuple[int, Dict[str, str]]] = []
    for r in rows:
        msg = _first_line(r.get("message", ""))
        key_hint = None
        # crude key extraction: WORD-123 style
        for part in msg.split():
            if "-" in part and part.split("-")[0].isalpha():
                key_hint = part.strip(",.;:()[]{}")
                break
        dedup_key = key_hint or r.get("displayId") or r.get("id", "")[:10]
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        scored.append((_score_commit(msg), {
            "repo": r.get("repo", ""),
            "display": r.get("displayId") or r.get("id", "")[:10],
            "author": r.get("author") or r.get("authorEmail", ""),
            "ts": r.get("authorTimestamp", ""),
            "key": key_hint or "",
            "line": _truncate(msg),
        }))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [s[1] for s in scored[:top_n]]

# ------------------ Context, fingerprint, tokens ------------------

def build_context(
    summary_rows: List[Dict[str, Any]],
    repo_csv_map: Dict[str, Path],
    window: Tuple[datetime, datetime],
    branches_label: str,
    fix_version: Optional[str],
    top_n_per_repo: int = 15,
) -> Dict[str, Any]:
    start_utc, end_utc = window
    repos_ctx = []
    for sr in summary_rows:
        repo = sr.get("repo", "")
        csv_path = repo_csv_map.get(repo) or Path(sr.get("csv_path", ""))
        highlights = select_highlights(csv_path, top_n=top_n_per_repo)
        repos_ctx.append({
            "project": sr.get("project", ""),
            "repo": repo,
            "branch": sr.get("branch", ""),
            "count": int(sr.get("count", 0) or 0),
            "highlights": highlights,
        })
    return {
        "fix_version": fix_version or "",
        "window": {
            "start": start_utc.isoformat(),
            "end": end_utc.isoformat(),
        },
        "branches": branches_label,
        "repos": repos_ctx,
    }

def context_fingerprint(ctx: Dict[str, Any]) -> str:
    """Stable fingerprint for caching (order keys to make deterministic)."""
    payload = json.dumps(ctx, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def estimate_tokens_from_chars(chars: int) -> int:
    # crude but safe: ~4 chars/token
    return max(1, chars // 4)

# ------------------ LLM call ------------------

def _make_prompt(ctx: Dict[str, Any]) -> Tuple[str, str]:
    system = (
        "You are a release auditor. Write concise, accurate summaries from structured context. "
        "Prioritize clarity, business impact, and testing guidance. Avoid guessing. "
        "If information is missing, state that briefly and continue."
    )
    user = (
        "CONTEXT (JSON):\n"
        f"{json.dumps(ctx, indent=2, ensure_ascii=False)}\n\n"
        "Write a release narrative with the following sections:\n\n"
        "1) Executive Summary (5–8 bullets)\n"
        "   - Call out which repos saw the most change and why (based on commit text).\n"
        "   - Mention major themes: features, fixes, refactors.\n"
        "2) Repo Highlights\n"
        "   - For each repo, list 3–5 notable items: \"**<short id>** — <one-line summary>\".\n"
        "3) Potential Risks & Test Focus\n"
        "   - Deduce plausible risk areas (e.g., payment flows, data migrations).\n"
        "   - Recommend specific test areas.\n"
        "4) Notable Cross‑Repo Links (if detected)\n"
        "   - List stories/terms appearing across multiple repos, if any.\n\n"
        "Constraints:\n"
        "- Use only what’s in CONTEXT.\n"
        "- Don’t invent Jira details you don’t see.\n"
        "- Keep total length under ~700 words."
    )
    return system, user

def _openai_chat(model: str, system: str, user: str, max_tokens: int) -> str:
    # Optional dependency – keep failure graceful.
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("openai package is not installed; cannot write LLM summary.") from e
    settings = Settings()  # loads API key from .env via pydantic-settings
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""

# ------------------ Cache + writer ------------------

def _cache_key(model: str, fp: str) -> str:
    return f"llm:summary|model={model}|fp={fp}"

def write_markdown(text: str, output_dir: Path, base_name: str = "release_audit_llm") -> Path:
    out = output_dir / f"{base_name}.md"
    out.write_text(text, encoding="utf-8")
    return out

def build_llm_summary(
    summary_rows: List[Dict[str, Any]],
    output_dir: Path,
    window: Tuple[datetime, datetime],
    branches_label: str,
    repo_csv_map: Dict[str, Path],
    model: str = "gpt-4o-mini",
    max_tokens: int = 1200,
    budget_cents: int = 10,
    top_n_per_repo: int = 15,
    base_name: str = "release_audit_llm",
    fix_version: Optional[str] = None,
) -> Path:
    """
    Builds a compact context from CSVs, enforces budget, caches the LLM output, and writes a markdown narrative.
    Returns the markdown path.
    """
    ctx = build_context(summary_rows, repo_csv_map, window, branches_label, fix_version, top_n_per_repo=top_n_per_repo)
    # crude token estimate
    sys_prompt, user_prompt = _make_prompt(ctx)
    approx_tokens = estimate_tokens_from_chars(len(sys_prompt) + len(user_prompt)) + max_tokens

    # Budget guard: assume model≈$0.15 per 1k tokens (safe ceiling for minis); adjust if you track live prices
    est_cents = int((approx_tokens / 1000.0) * 15)
    if est_cents > budget_cents:
        # Try to reduce by lowering highlights; if still too big, bail gracefully.
        if top_n_per_repo > 8:
            return build_llm_summary(
                summary_rows, output_dir, window, branches_label, repo_csv_map,
                model=model, max_tokens=max_tokens, budget_cents=budget_cents,
                top_n_per_repo=8, base_name=base_name, fix_version=fix_version
            )
        raise RuntimeError(
            f"Estimated LLM cost ~{est_cents}¢ exceeds budget ({budget_cents}¢). "
            "Re-run with --llm-budget-cents higher or fewer highlights."
        )

    # Cache: fingerprint the context (highlights, counts, window)
    fp = context_fingerprint(ctx)
    key = _cache_key(model, fp)

    def _fetch() -> Dict[str, Any]:
        text = _openai_chat(model=model, system=sys_prompt, user=user_prompt, max_tokens=max_tokens)
        return {"text": text}

    data, source = load_cache_or_call(
        key=key,
        ttl_hours=720,  # 30 days
        fetch_fn=_fetch,
        force_refresh=False,
    )

    text = data.get("text", "").strip()
    if not text:
        raise RuntimeError("LLM returned empty summary.")
    return write_markdown(text, output_dir, base_name=base_name)
