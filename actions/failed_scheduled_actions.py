# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Report failed GitHub Actions on default branches across an organization."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

FAILED_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure", "cancelled"}


def parse_visibility(visibility_input, repo_visibility):
    """Parse and validate repository visibility settings."""
    valid = {"public", "private", "internal", "all"}
    stripped = [v.strip() for v in visibility_input.lower().split(",") if v.strip()]
    repo_visibility = (repo_visibility or "").lower()

    if invalid := [v for v in stripped if v not in valid]:
        print(f"⚠️  Invalid visibility values: {', '.join(invalid)} - ignoring")

    visibility_list = [v for v in stripped if v in valid]
    if not visibility_list:
        print("⚠️  No valid visibility values, defaulting to 'public'")
        return ["public"]

    if repo_visibility == "public" and visibility_list != ["public"]:
        print("⚠️  Security: Public repo cannot inspect non-public repos. Restricting to public only.")
        return ["public"]

    return visibility_list


def get_repo_filter(visibility_list):
    """Return filtering strategy for repository visibility."""
    if len(visibility_list) == 1 and visibility_list[0] != "all":
        return {"filter": None, "str": visibility_list[0]}

    filter_set = {"public", "private", "internal"} if "all" in visibility_list else set(visibility_list)
    return {"filter": filter_set, "str": "all" if "all" in visibility_list else ", ".join(sorted(visibility_list))}


def format_repo_heading(repo_name, repo_url):
    """Format a repository section heading for GitHub report Markdown."""
    return f"## 📦 [{repo_name.rsplit('/', 1)[-1]}]({repo_url})"


def run_time(run):
    """Return the run timestamp used for recency filtering and latest-run selection."""
    value = run.get("run_started_at") or run.get("created_at") or ""
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else datetime.min.replace(tzinfo=timezone.utc)


def github_get(path, params=None, token=None, allow_skip=False):
    """Fetch JSON from the GitHub REST API."""
    token = token or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN or GITHUB_TOKEN is required")

    url = f"https://api.github.com{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore").lower()
        rate_limited = e.code == 403 and (e.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in body)
        if allow_skip and e.code in {403, 404} and not rate_limited:
            print(f"Skipping {path}: {e.code}")
            return None
        raise


def paginate(path, params=None, key=None, max_pages=100, token=None, allow_skip=False):
    """Collect paginated GitHub API results."""
    items = []
    for page in range(1, max_pages + 1):
        data = github_get(path, {**(params or {}), "per_page": 100, "page": page}, token=token, allow_skip=allow_skip)
        if not data:
            break
        page_items = data[key] if key else data
        items.extend(page_items)
        if len(page_items) < 100:
            break
        time.sleep(0.2)
    return items


def collect_failed_actions(
    org="ultralytics", visibility="public", repo_visibility="public", max_run_pages=3, days=1, token=None
):
    """Collect latest failed workflow runs on each non-archived repo's default branch."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    filter_config = get_repo_filter(parse_visibility(visibility, repo_visibility))
    repos = [
        r
        for r in paginate(f"/orgs/{org}/repos", {"type": "all"}, token=token)
        if not r.get("archived") and (not filter_config["filter"] or r["visibility"].lower() in filter_config["filter"])
    ]
    failures = []
    for repo in repos:
        full_name = repo["full_name"]
        branch = repo.get("default_branch") or "main"
        runs = paginate(
            f"/repos/{full_name}/actions/runs",
            {"branch": branch},
            key="workflow_runs",
            max_pages=max_run_pages,
            token=token,
            allow_skip=True,
        )
        latest = {}
        for run in runs:
            key = run.get("workflow_id") or run.get("name")
            current = latest.get(key)
            if not current or run_time(run) > run_time(current):
                latest[key] = run

        for run in latest.values():
            if run.get("conclusion") in FAILED_CONCLUSIONS and (not cutoff or run_time(run) >= cutoff):
                failures.append(
                    {
                        "repo": full_name,
                        "repo_url": repo.get("html_url") or f"https://github.com/{full_name}",
                        "visibility": repo.get("visibility", "private" if repo.get("private") else "public"),
                        "workflow": run.get("name") or run.get("display_title") or "Workflow",
                        "event": run.get("event") or "unknown",
                        "branch": branch,
                        "run_number": run.get("run_number"),
                        "failed_at": run.get("updated_at") or run.get("created_at") or "",
                        "sha": (run.get("head_sha") or "")[:7],
                        "title": run.get("display_title") or "",
                        "url": run.get("html_url"),
                    }
                )
    return sorted(failures, key=lambda x: (x["repo"].lower(), x["workflow"].lower()))


def format_report(failures, org="ultralytics"):
    """Format failed workflow runs as Markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Failed Default Branch Actions",
        "",
        f"Failed workflow runs on default branches for `{org}` repositories as of {now}.",
        "",
    ]
    if not failures:
        lines.append("No failed default-branch workflow runs found.")
        return "\n".join(lines) + "\n"

    repo_count = len({failure["repo"] for failure in failures})
    run_word = "run" if len(failures) == 1 else "runs"
    repo_word = "repository" if repo_count == 1 else "repositories"
    event_counts = Counter(failure.get("event") or "unknown" for failure in failures)
    lines.extend(
        [
            f"**{len(failures)} failing default-branch workflow {run_word}** across **{repo_count} {repo_word}**.",
            "**By Event:** " + " | ".join(f"`{event}` {event_counts[event]}" for event in sorted(event_counts)),
        ]
    )
    grouped = defaultdict(list)
    for failure in failures:
        grouped[failure["repo"]].append(failure)

    for repo, repo_failures in grouped.items():
        lines.extend(
            [
                "",
                format_repo_heading(
                    repo,
                    repo_failures[0].get("repo_url") or f"https://github.com/{repo}",
                ),
            ]
        )
        for failure in repo_failures:
            failed_at = failure["failed_at"].replace("T", " ").replace("Z", " UTC")
            details = f" @ `{failure['sha']}`" if failure["sha"] else ""
            details += f" - {failure['title']}" if failure["title"] else ""
            lines.append(
                f"- **{failure['workflow']}** (`{failure.get('event') or 'unknown'}`) on `{failure['branch']}` "
                f"failed at {failed_at}{details}. "
                f"[Run #{failure['run_number']}]({failure['url']})"
            )
    return "\n".join(lines) + "\n"


def run():
    """Write failed Actions report to stdout and the GitHub step summary."""
    org = os.getenv("ORG", "ultralytics")
    max_run_pages = int(os.getenv("MAX_RUN_PAGES", "3"))
    days = int(os.getenv("REPORT_DAYS", "1"))
    report = format_report(
        collect_failed_actions(
            org,
            visibility=os.getenv("VISIBILITY", "public"),
            repo_visibility=os.getenv("REPO_VISIBILITY", "public"),
            max_run_pages=max_run_pages,
            days=days,
        ),
        org,
    )
    print(report)
    if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a") as f:
            f.write("\n" + report)


if __name__ == "__main__":
    run()
