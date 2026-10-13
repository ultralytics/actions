# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Post a Slack alert for a failed GitHub Actions run, with an AI triage of its failed job logs."""

from __future__ import annotations

import os
import re

import requests

from actions.utils import GITHUB_API_URL, Action, get_response

FAILED_CONCLUSIONS = {"failure", "timed_out"}
MAX_LOG_JOBS = 10  # jobs whose logs are read; every failed job is still listed with its URL
LOG_CHARS = 60000  # log tail budget shared by the jobs read, so a single failure gets a deeper tail
MAX_JOB_LOG_CHARS = 20000
LOG_NOISE = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z |\x1b\[[0-9;]*[A-Za-z]", re.MULTILINE)  # timestamps, colors
PROMPT = """Triage this failed GitHub Actions run for the maintainers' chat alert, using the run details and failed job logs below.

Reply in GitHub-flavored Markdown in at most 150 words, using only the detail the failure needs, with no headings, tables, emoji (drop any from quoted text) or preamble:
- Line 1: `**<Bug|Transient|Unclear>** - <what failed and its decisive error, in one short sentence>`
  - Bug: a re-run of the same commit would fail again until something changes, such as the code, tests, build configuration, workflow or a dependency release.
  - Transient: every failed job is explained by the available logs and a re-run would likely pass, such as a network, registry or rate-limit error, or a runner fault. Missing or unexplained failures require Unclear, even if other jobs look transient.
  - Unclear: the logs do not show the cause, for example when they are cut off or missing.
  - If jobs fail for different reasons, Line 1 covers the most actionable one (Bug, then Unclear, then Transient).
- Then up to 4 bullets as needed: decisive evidence, the likely root cause, a fix or next diagnostic check, and any other distinct failure. Distinguish confirmed facts from hypotheses and say when the logs do not establish the cause. Group matrix jobs that fail the same way.

Rules:
- Ground every claim in the run details or logs. The cause is the earliest error the failure follows from; errors the run recovered from, such as retried downloads, are noise, and later test failures, teardown errors and lines like "Process completed with exit code 1" are its symptoms.
- Quote errors, test names and identifiers in inline code.
- Link each failed job you name to its job URL. Link only the URLs in the run details, or a repository file named in the logs as {repo_url}/blob/{sha}/<path>#L<line> with <path> relative to the repository root (drop runner checkout prefixes like /home/runner/work/<name>/<name>/). Never invent URLs, issue or PR numbers, versions or commands."""


def get_log_tail(event: Action, repo: str, job_id: int, chars: int) -> str:
    """Return the end of a job's log before post-job cleanup, where the failure usually is."""
    r = event.get(f"{GITHUB_API_URL}/repos/{repo}/actions/jobs/{job_id}/logs")
    if r.status_code != 200:
        return f"(log unavailable: HTTP {r.status_code})"
    log = r.content.decode(errors="replace")  # served as text/plain without a charset, which requests reads as Latin-1
    return LOG_NOISE.sub("", log.split("Post job cleanup.")[0])[-chars:]


def analyze_run(event: Action, run: dict) -> str:
    """Return a Markdown triage of the run's failed jobs, or an empty string without an API key or a failed job."""
    if event.should_skip_llm():
        return ""
    # A recovered or cancelled rerun still needs the original failure's logs.
    attempt = run["run_attempt"] if run.get("conclusion") in FAILED_CONCLUSIONS else 1
    jobs = event.paginate(f"{run['url']}/attempts/{attempt}/jobs", key="jobs", hard=True)
    failed = [job for job in jobs if job.get("conclusion") in FAILED_CONCLUSIONS]
    if not failed:
        return ""

    repo = run["repository"]["full_name"]
    sha, repo_url = run["head_sha"], run["repository"]["html_url"]
    title = ((run.get("head_commit") or {}).get("message") or "").split("\n")[0]
    details = [
        f"Repository: {repo}",
        f"Workflow: {run['name']} run #{run['run_number']} ({run['event']} on {run['head_branch']}): {run['html_url']}",
        f"Commit: {repo_url}/commit/{sha} {title}",
        (
            f"Current attempt: {run['run_attempt']}, conclusion: {run.get('conclusion')}; logs from attempt {attempt}. "
            "Report this observed result; a passed rerun confirms recovery but does not prove the root cause is fixed."
        ),
        "Failed jobs:",
    ]
    for job in failed:
        step = next((s["name"] for s in job.get("steps") or [] if s.get("conclusion") in FAILED_CONCLUSIONS), None)
        details.append(f"- {job['name']}{f' (step: {step})' if step else ''}: {job['html_url']}")
    read = failed[:MAX_LOG_JOBS]
    chars = min(MAX_JOB_LOG_CHARS, LOG_CHARS // len(read))
    logs = [f"### Log tail: {job['name']}\n{get_log_tail(event, repo, job['id'], chars)}" for job in read]

    prompt = "\n\n".join([PROMPT.format(repo_url=repo_url, sha=sha), "\n".join(details), *logs])
    # A user message, not a system one: get_response appends Ultralytics-specific guidance to system prompts
    return get_response([{"role": "user", "content": prompt}], check_links=False).strip()


def to_mrkdwn(markdown: str) -> str:
    """Convert the Markdown bullets, bold and links of a model reply to Slack mrkdwn."""
    text = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # Slack control characters
    text = re.sub(r"^([ \t]*)[-*+] ", r"\1• ", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"<\2|\1>", text)


def run(event: Action | None = None, slack_webhook: str | None = None, mention: str = ""):
    """Retry completed failures once, then report the result and triage when the rerun completes."""
    source = event.event_data.get("workflow_run") if event else None
    event = event or Action()
    if source and (
        source["run_attempt"] > 2 or (source["run_attempt"] == 1 and source["conclusion"] not in FAILED_CONCLUSIONS)
    ):
        return
    if source:
        icon = "✅" if source["conclusion"] == "success" else "❌"
        text = (
            f"{mention + ' ' if mention else ''}*{to_mrkdwn(source['name'])}* {icon} "
            f"`{source['repository']['full_name']}`  <{source['html_url']}|*Run*>"
        )
    else:
        text = os.environ["ALERT_TEXT"]
    try:
        if source and source["run_attempt"] == 2:
            original = event.get(f"{source['url']}/attempts/1", hard=True).json()
            if original["conclusion"] not in FAILED_CONCLUSIONS:
                return
        run_info = (
            source
            or event.get(
                f"{GITHUB_API_URL}/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
                hard=True,
            ).json()
        )
        analysis = analyze_run(event, run_info)
    except Exception as e:  # the alert matters more than its analysis
        print(f"::warning::Failure analysis skipped: {e}")
        analysis = ""
    if source:
        if source["run_attempt"] == 2:
            outcome = "Passed" if source["conclusion"] == "success" else source["conclusion"]
            text += f"\n*Rerun result: {outcome}* — <{source['html_url']}/attempts/2|Attempt 2>"
        elif analysis.startswith("**Transient** -"):
            try:
                if event.get(source["url"], hard=True).json()["run_attempt"] != 1:
                    return  # a manual rerun already owns the next completion event
                event.post(f"{source['url']}/rerun-failed-jobs", hard=True)
                print("Transient failure: rerun requested; Slack will report when attempt 2 completes.")
                return
            except requests.RequestException as e:
                print(f"::warning::Automatic rerun unavailable: {e}")
                text += "\nAutomatic rerun could not be confirmed; check the linked run."
    if analysis:
        print(analysis)
        if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary_file, "a") as f:
                f.write(f"## Failure Analysis\n\n{analysis}\n")
        text += "\n" + to_mrkdwn(analysis)
    requests.post(slack_webhook or os.environ["SLACK_WEBHOOK"], json={"text": text}, timeout=30).raise_for_status()


if __name__ == "__main__":
    run()
