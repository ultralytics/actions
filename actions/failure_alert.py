# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Post a Slack alert for a failed GitHub Actions run, with an AI triage of its failed job logs."""

from __future__ import annotations

import os
import re
import signal

import requests

from actions.utils import GITHUB_API_URL, Action, get_response

FAILED_CONCLUSIONS = {"failure", "timed_out"}
TIMEOUT = "The job has exceeded the maximum execution time"  # annotation of a job cancelled at its timeout-minutes
MAX_LOG_JOBS = 10  # jobs whose logs are read; every failed job is still listed with its URL
LOG_CHARS = 60000  # log tail budget shared by the jobs read, so a single failure gets a deeper tail
MAX_JOB_LOG_CHARS = 20000
LOG_NOISE = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z |\x1b\[[0-9;]*[A-Za-z]", re.MULTILINE)  # timestamps, colors
PROMPT = """Triage this failed GitHub Actions run for the maintainers' chat alert, using the run details and failed job logs below.

Reply in GitHub-flavored Markdown in at most 150 words, using only the detail the failure needs, with no headings, tables, emoji (drop any from quoted text) or preamble:
- Line 1: `**<Bug|Transient|Unclear>** - <what failed and its decisive error, in one short sentence>`
  - Bug: a re-run of the same commit would fail again until something changes, such as the code, tests, build configuration, workflow or a dependency release.
  - Transient: every failed job is explained by the available logs and a re-run would likely pass, such as a network, registry or rate-limit error, or a runner fault like a lost runner connection. A logged timeout connecting to an external service, such as a database, explains its failure. Missing or unexplained failures require Unclear, even if other jobs look transient.
  - Unclear: the logs do not show the cause, for example when they are cut off or missing.
  - If jobs fail for different reasons, Line 1 covers the most actionable one (Bug, then Unclear, then Transient).
- Then up to 4 bullets as needed: decisive evidence, the likely root cause, a fix or next diagnostic check, and any other distinct failure. Distinguish confirmed facts from hypotheses and say when the logs do not establish the cause. Group matrix jobs that fail the same way.

Rules:
- Ground every claim in the run details or logs. The cause is the earliest error the failure follows from; errors the run recovered from, such as retried downloads, are noise, and later test failures, teardown errors and lines like "Process completed with exit code 1" are its symptoms.
- Quote errors, test names and identifiers in inline code.
- Link each failed job you name to its job URL. Link only the URLs in the run details, or a repository file named in the logs as {repo_url}/blob/{sha}/<path>#L<line> with <path> relative to the repository root (drop runner checkout prefixes like /home/runner/work/<name>/<name>/). Never invent URLs, issue or PR numbers, versions or commands."""


def get_log_tail(event: Action, repo: str, job_id: int, chars: int) -> str:
    """Return the end of a job's log before post-job cleanup, or the job's annotations when GitHub kept no log."""
    r = event.get(f"{GITHUB_API_URL}/repos/{repo}/actions/jobs/{job_id}/logs")
    if r.status_code != 200:  # a runner that lost contact uploads no log, but its annotation still says why
        notes = event.get(f"{GITHUB_API_URL}/repos/{repo}/check-runs/{job_id}/annotations")
        messages = [note["message"] for note in notes.json()] if notes.status_code == 200 else []
        return "\n".join([f"(log unavailable: HTTP {r.status_code})", *messages])
    log = r.content.decode(errors="replace")  # served as text/plain without a charset, which requests reads as Latin-1
    return LOG_NOISE.sub("", log.split("Post job cleanup.")[0])[-chars:]


def get_failed_jobs(event: Action, run: dict) -> list[dict]:
    """Return the run attempt's failed jobs, marking a job GitHub cancelled at its timeout-minutes as timed_out."""
    repo = run["repository"]["full_name"]
    jobs = event.paginate(f"{run['url']}/attempts/{run['run_attempt']}/jobs", key="jobs", hard=True)
    for job in jobs:  # only an annotation tells a timeout from a manual or concurrency cancel
        if job.get("conclusion") == "cancelled":
            notes = event.paginate(f"{GITHUB_API_URL}/repos/{repo}/check-runs/{job['id']}/annotations", hard=True)
            if any(TIMEOUT in note["message"] for note in notes):
                job["conclusion"] = "timed_out"
    return [job for job in jobs if job.get("conclusion") in FAILED_CONCLUSIONS]


def analyze_run(event: Action, run: dict) -> str:
    """Return a Markdown triage of the run's failed jobs, or an empty string without an API key or a failed job."""
    if event.should_skip_llm():
        return ""
    failed = get_failed_jobs(event, run)
    if not failed:
        return ""

    repo = run["repository"]["full_name"]
    sha, repo_url = run["head_sha"], run["repository"]["html_url"]
    title = ((run.get("head_commit") or {}).get("message") or "").split("\n")[0]
    details = [
        f"Repository: {repo}",
        f"Workflow: {run['name']} run #{run['run_number']} ({run['event']} on {run['head_branch']}): {run['html_url']}",
        f"Commit: {repo_url}/commit/{sha} {title}",
        f"Attempt: {run['run_attempt']}, conclusion: {run.get('conclusion')}",
        "Failed jobs:",
    ]
    for job in failed:
        step = next(
            (s["name"] for s in job.get("steps") or [] if s.get("conclusion") in {*FAILED_CONCLUSIONS, "cancelled"}),
            None,
        )
        details.append(f"- {job['name']} ({job['conclusion']}{f', step: {step}' if step else ''}): {job['html_url']}")
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


def run(
    event: Action | None = None,
    slack_webhook: str | None = None,
    mention: str = "",
    analysis_timeout: int = 0,
    rerun: bool = False,
):
    """Alert a failed run with its triage, or retry it once and alert only if the retry fails too."""
    source = event.event_data.get("workflow_run") if event else None
    event = event or Action()
    # Only failures alert, and of reruns only the one this App requested: a manual rerun already follows an alert
    if source and (
        source["conclusion"] not in {*FAILED_CONCLUSIONS, "cancelled"}
        or source["run_attempt"] > 2
        or (source["run_attempt"] == 2 and (not rerun or source["triggering_actor"]["type"] != "Bot"))
        or (  # a cancelled run alerts only when a job hit its timeout-minutes, not on a manual or concurrency cancel
            source["conclusion"] == "cancelled"
            and all(job["conclusion"] != "timed_out" for job in get_failed_jobs(event, source))
        )
    ):
        return
    if source:
        text = (
            f"{mention + ' ' if mention else ''}*{to_mrkdwn(source['name'])}* ❌ "
            f"`{source['repository']['full_name']}`  <{source['html_url']}|*Run*>"
        )
    else:
        text = os.environ["ALERT_TEXT"]
    if analysis_timeout:  # the App runs this in a dedicated Unix child process

        def expire_analysis(_signum, _frame):
            raise RuntimeError("Failure analysis deadline exceeded")

        previous_handler = signal.signal(signal.SIGALRM, expire_analysis)
        signal.alarm(analysis_timeout)
    try:
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
    finally:
        if analysis_timeout:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
    if source:
        if source["run_attempt"] == 2:
            text += f"\n*Failed on both attempts*: the automatic <{source['html_url']}/attempts/2|rerun> failed too."
        elif rerun and analysis.startswith("**Transient** -"):
            try:
                if event.get(source["url"], hard=True).json()["run_attempt"] != 1:
                    return  # already rerun, by hand or by a retried task, and that attempt owns the result
                event.post(f"{source['url']}/rerun-failed-jobs", hard=True)
                print(
                    f"Rerun requested for {source['html_url']}; Slack alerts only if attempt 2 fails too.\n{analysis}"
                )
                return
            except requests.RequestException as e:
                print(f"::warning::Automatic rerun unavailable: {e}")
                text += "\nAutomatic rerun could not be confirmed; check the linked run."
    if analysis:
        if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary_file, "a") as f:
                f.write(f"## Failure Analysis\n\n{analysis}\n")
        text += "\n" + to_mrkdwn(analysis)
    print(text)
    requests.post(slack_webhook or os.environ["SLACK_WEBHOOK"], json={"text": text}, timeout=30).raise_for_status()


if __name__ == "__main__":
    run()
