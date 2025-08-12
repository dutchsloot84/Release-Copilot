import os
import streamlit as st
from dotenv import load_dotenv
from datetime import date
from typing import Optional
from .ui_backend import RunThread, tail_file

# Import the callable pipeline
from release_copilot.app import run_release_audit  # relies on your refactor above
from release_copilot.config.settings import load_query_presets

load_dotenv()

st.set_page_config(page_title="Release Copilot (Local POC)", layout="wide")
st.title("🧰 Release Copilot — Local POC")

with st.expander("Environment status", expanded=False):
    missing = []
    for key in [
        "JIRA_BASE_URL",
        "ATLASSIAN_OAUTH_CLIENT_ID",
        "ATLASSIAN_OAUTH_CLIENT_SECRET",
        "JIRA_TOKEN_FILE",
        "BITBUCKET_BASE_URL",
        "BITBUCKET_EMAIL",
        "BITBUCKET_APP_PASSWORD",
    ]:
        if not os.getenv(key):
            missing.append(key)
    if missing:
        st.warning("Missing env vars: " + ", ".join(missing) + ". Run the wizard or edit your .env.")
    else:
        st.success("Core env vars present.")

st.subheader("Inputs")
col1, col2 = st.columns(2)
with col1:
    fix_version = st.text_input("Fix Version", value="r-55.1")
    project = st.text_input("Bitbucket Project", value="STARSYSONE")
    repo = st.text_input("Repository", value="claimcenter")
with col2:
    branch = st.text_input("Branch", value="release/r-55.1")
    since_date: Optional[date] = st.date_input("Changes since (optional)", value=None)
    since = since_date.isoformat() if since_date else None

presets = load_query_presets()
st.subheader("JQL")
c1, c2 = st.columns([1, 2])
with c1:
    preset_name = st.selectbox("Preset", options=["(none)"] + sorted(list(presets.keys())))
with c2:
    custom_jql = st.text_area("Custom JQL (overrides preset)", value="", height=100, placeholder='Leave blank to use preset or default')

adv = st.expander("Advanced", expanded=False)
with adv:
    enable_confluence = st.checkbox("Publish to Confluence (optional)", value=False)
    enable_llamaindex = st.checkbox("Enable LlamaIndex context (optional)", value=False)
    dry_run = st.checkbox("Dry run (skip LLM; validate plumbing)", value=False)

run_clicked = st.button("▶️ Run audit", type="primary")

status = st.empty()
log_box = st.empty()
result_box = st.container()

if "runner" not in st.session_state:
    st.session_state.runner = None

def render_logs(log_path: str):
    content = tail_file(log_path) if log_path else ""
    if not content:
        log_box.info("Waiting for logs...")
    else:
        log_box.text_area("Live logs (tail)", content, height=300)

if run_clicked:
    # Kick off background run
    jql_to_use = custom_jql.strip() if custom_jql.strip() else (presets.get(preset_name) if preset_name != "(none)" else None)
    kwargs = dict(
        fix_version=fix_version,
        project=project,
        repo=repo,
        branch=branch,
        since=since,
        jql=jql_to_use,
        enable_confluence=enable_confluence,
        enable_llamaindex=enable_llamaindex,
        dry_run=dry_run,
    )
    runner = RunThread(target=run_release_audit, kwargs=kwargs)
    st.session_state.runner = runner
    runner.start()
    status.info("Running… this usually takes a few minutes.")

# Poll while running
runner = st.session_state.runner
if runner:
    while runner.is_alive():
        # try to render logs if the pipeline already created a log file
        # assume logs path is logs/release-copilot.log
        render_logs("logs/release-copilot.log")
        st.sleep(0.5)
    # one last log render
    render_logs("logs/release-copilot.log")

    if runner.error:
        status.error(f"Run failed: {runner.error}")
    else:
        res = runner.result or {}
        if not res.get("ok", False):
            status.error(f"Run finished with errors: {res.get('error')}")
        else:
            status.success("Run complete!")
            artifacts = res.get("artifacts", {})
            counts = res.get("counts", {})
            cost = res.get("cost", {})

            with result_box:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Jira issues", counts.get("jira_total", 0))
                c2.metric("Commits", counts.get("commits_total", 0))
                c3.metric("Missing in Git", counts.get("missing_in_git", 0))
                c4.metric("Commits w/o Story", counts.get("commits_without_story", 0))

                st.markdown("### Artifacts")
                excel_path = artifacts.get("excel")
                md_path = artifacts.get("markdown")

                if excel_path and os.path.exists(excel_path):
                    with open(excel_path, "rb") as f:
                        st.download_button("⬇️ Download Excel", f, file_name=os.path.basename(excel_path))
                if md_path and os.path.exists(md_path):
                    with open(md_path, "rb") as f:
                        st.download_button("⬇️ Download Markdown", f, file_name=os.path.basename(md_path))

                if cost:
                    st.markdown("### Cost Summary")
                    st.json(cost)

            # reset runner so button can be used again
            st.session_state.runner = None
