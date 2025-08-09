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
python -m src.config.env_wizard
python -m src.app --fix-version r-55.1 --project STARSYSONE --repo claimcenter --branch release/r-55.1
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

streamlit run src/ui/streamlit_app.py --server.port 8502
```

Troubleshooting:
- Ensure Python 3.11+ and `pip` are on PATH.
- Corporate proxy/SSL: set `HTTP_PROXY/HTTPS_PROXY` and `REQUESTS_CA_BUNDLE` if needed.

## Example

```bash
python -m src.app --fix-version r-55.1 --project STARSYSONE --repo claimcenter --branch release/r-55.1 --since 2025-07-01
```

## Cost
A full run typically costs **$0.25–$0.80** depending on models. Re-running with cached API results costs near $0.

## Troubleshooting
* SSL issues: ensure your enterprise certificates are installed.
* Proxy: set `HTTPS_PROXY` env var.
* Bad credentials: rerun `python -m src.config.env_wizard`.

## Optional features
* Confluence publishing: enable by setting `CONFLUENCE_ENABLED=true` in `.env` or passing `--enable-confluence`.
* LlamaIndex: toggle with `ENABLE_LLAMAINDEX=true`.
