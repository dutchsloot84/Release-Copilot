# Release Copilot

Local proof-of-concept that audits a release by fetching Jira issues and Bitbucket commits, comparing them and producing Excel + Markdown output. Runs entirely on a developer laptop.

```
+---------+        +------------+        +--------------+
|  Planner|------->| Jira/Git   |------->| Report Writer|
+---------+        +------------+        +--------------+
                                     \
                                      +--> Confluence (optional)
```

## Quickstart

```bash
pip install -r requirements.txt
python -m release_copilot.config.env_wizard
python -m release_copilot.app --fix-version r-55.1 --project STARSYSONE --repo claimcenter --branch release/r-55.1
```

Artifacts are written to `data/outputs/release_audit.xlsx` and `release_report.md`.

## One-Click UI (Local)

**Windows**
- Double-click: `scripts/run_ui.bat`
- First launch runs a setup wizard if `.env` is missing.

**macOS/Linux**
```bash
chmod +x scripts/run_ui.sh
./scripts/run_ui.sh

If port 8501 is busy, run:

streamlit run src/release_copilot/ui/streamlit_app.py --server.port 8502
```

Troubleshooting:
- Ensure Python 3.11+ and `pip` are on PATH.
- Corporate proxy/SSL: set `HTTP_PROXY/HTTPS_PROXY` and `REQUESTS_CA_BUNDLE` if needed.

## Local CLI (one click)

**Windows**
- Double-click: `scripts/run_local.bat`
- First run triggers the setup wizard.

**macOS/Linux**
```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh --help
```

Both scripts install requirements, perform an editable install, then run:

```
Wizard: python -m release_copilot.config.env_wizard
App:    python -m release_copilot.app
```

## Example

```bash
python -m release_copilot.app --fix-version r-55.1 --project STARSYSONE --repo claimcenter --branch release/r-55.1 --since 2025-07-01
```

### JQL options

Default (uses `DEFAULT_JQL` with `{fix_version}`):

```bash
python -m release_copilot.app --fix-version "Mobilitas 2025.08.22" --project STARSYSONE --repo claimcenter --branch release/r-55.1
```

Use preset:

```bash
python -m release_copilot.app --fix-version "Mobilitas 2025.08.22" --jql-preset mobilitas_standard
```

Custom JQL (Windows quoting tip):

```bash
python -m release_copilot.app --jql "project = MOBI AND fixVersion = \"Mobilitas 2025.08.22\" AND statusCategory != Done"
```

On PowerShell, escape inner quotes as `\"...\"`. On bash, you can wrap the whole string in single quotes.

Streamlit UI: select a preset or paste a custom JQL; custom overrides the preset.

## Cost
A full run typically costs **$0.25–$0.80** depending on models. Re-running with cached API results costs near $0.

## Troubleshooting
* SSL issues: ensure your enterprise certificates are installed.
* Proxy: set `HTTPS_PROXY` env var.
* Bad credentials: rerun `python -m release_copilot.config.env_wizard`.

## Optional features
* Confluence publishing: enable by setting `CONFLUENCE_ENABLED=true` in `.env` or passing `--enable-confluence`.
* LlamaIndex: toggle with `ENABLE_LLAMAINDEX=true`.

## Audit from JSON config

`release_copilot.commands.audit_from_config` reads a config file that
lists repositories and default branches, then fetches commits for each
repo/branch pair. A minimal config:

```json
{
  "repos": {
    "STARSYSONE/policycenter": "PC",
    "STARSYSONE/contactmanager": "CM"
  },
  "release_branch": "release/r-55.0",
  "develop_branch": "develop"
}
```

CLI overrides take precedence over config values. Branch selection is
mutually exclusive: use `--develop-only` or `--release-only`; without either
flag both branches are processed (release first). Repos are always taken from
the config.

Results are cached under `data/.cache` using a key composed of project,
repo, branch and date window. Control cache behaviour with
`--cache-ttl-hours` and `--force-refresh`.

Example:

```bash
# Run both release and develop for all repos in config.json
python -m release_copilot.commands.audit_from_config \
  --config config/release_audit_config.json \
  --cache-ttl-hours 12

# Release only, override release branch and force-refresh cache
python -m release_copilot.commands.audit_from_config \
  --config config/release_audit_config.json \
  --release-only \
  --release-branch release/r-55.1 \
  --force-refresh

# Develop only, override both branches from CLI (develop-only means only develop is used)
python -m release_copilot.commands.audit_from_config \
  --config config/release_audit_config.json \
  --develop-only \
  --develop-branch develop
```

### Optional LLM Narrative (Hybrid Mode)

By default, the audit writes CSV/Markdown/Excel for **$0**.

Enable an **LLM-written narrative** only when you want it:

```bash
python -m release_copilot.commands.audit_from_config \
  --config config/release_audit_config.json \
  --release-only \
  --write-llm-summary --llm-model gpt-4o-mini --llm-budget-cents 8
```

Cost controls:

- Sends only compact highlights (top N lines per repo), not full logs.
- Enforces a hard budget (`--llm-budget-cents`), otherwise skips.
- Caches output by fingerprint — reruns are free unless highlights change.
