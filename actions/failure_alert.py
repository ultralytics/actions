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

Reply in GitHub-flavored Markdown in at most 3 short lines and 60 words, with no headings, tables, emoji (drop any from quoted text) or preamble:
- Line 1: `**<Bug|Transient|Unclear>** - <what failed and its decisive error, in one short sentence>`
  - Bug: a re-run of the same commit would fail again until something changes, such as the code, tests, build configuration, workflow or a dependency release.
  - Transient: a re-run would likely pass, such as a flaky or timing-sensitive test, a network, registry or rate-limit error, or a runner fault like lost communication or a shutdown.
  - Unclear: the logs do not show the cause, for example when they are cut off or missing.
  - If jobs fail for different reasons, Line 1 covers the most actionable one (Bug, then Unclear, then Transient).
- Then at most 2 bullets: the likely root cause, with the fix when the logs make it evident, and any other distinct failure. Group matrix jobs that fail the same way.

Rules:
- Ground every claim in the logs. The cause is the earliest error the failure follows from; errors the run recovered from, such as retried downloads, are noise, and later test failures, teardown errors and lines like "Process completed with exit code 1" are its symptoms.
- Quote errors, test names and identifiers in inline code.
- Link each failed job you name to its job URL. Link only the URLs in the run details, or a repository file named in the logs as {repo_url}/blob/{sha}/<path>#L<line> with <path> relative to the repository root (drop runner checkout prefixes like /home/runner/work/<name>/<name>/). Never invent URLs, issue or PR numbers, versions or commands."""


def get_log_tail(event: Action, repo: str, job_id: int, chars: int) -> str:
    """Return the end of a job's log before post-job cleanup, where the failure usually is."""
    r = event.get(f"{GITHUB_API_URL}/repos/{repo}/actions/jobs/{job_id}/logs")
    if r.status_code != 200:
        return f"(log unavailable: HTTP {r.status_code})"
    log = r.content.decode(errors="replace")  # served as text/plain without a charset, which requests reads as Latin-1
    return LOG_NOISE.sub("", log.split("Post job cleanup.")[0])[-chars:]


def analyze_run(repo: str, run_id: str) -> str:
    """Return a Markdown triage of the run's failed jobs, or an empty string without an API key or a failed job."""
    event = Action()
    if event.should_skip_llm():
        return ""
    run = event.get(f"{GITHUB_API_URL}/repos/{repo}/actions/runs/{run_id}", hard=True).json()
    jobs = event.paginate(run["jobs_url"], params={"filter": "latest"}, key="jobs", hard=True)
    failed = [job for job in jobs if job.get("conclusion") in FAILED_CONCLUSIONS]
    if not failed:
        return ""

    sha, repo_url = run["head_sha"], run["repository"]["html_url"]
    title = ((run.get("head_commit") or {}).get("message") or "").split("\n")[0]
    details = [
        f"Repository: {repo}",
        f"Workflow: {run['name']} run #{run['run_number']} ({run['event']} on {run['head_branch']}): {run['html_url']}",
        f"Commit: {repo_url}/commit/{sha} {title}",
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


def run():
    """Post the alert with the failure triage appended, or the bare alert when the analysis fails."""
    text = os.environ["ALERT_TEXT"]
    try:
        analysis = analyze_run(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_RUN_ID"])
    except Exception as e:  # the alert matters more than its analysis
        print(f"::warning::Failure analysis skipped: {e}")
        analysis = ""
    if analysis:
        print(analysis)
        if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary_file, "a") as f:
                f.write(f"## Failure Analysis\n\n{analysis}\n")
        text += "\n" + to_mrkdwn(analysis)
    requests.post(os.environ["SLACK_WEBHOOK"], json={"text": text}, timeout=30).raise_for_status()


if __name__ == "__main__":
    run()
