# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import time
from datetime import datetime

from .utils import GITHUB_API_URL, Action

# Configuration
RUN_CI_KEYWORD = "@ultralytics/run-ci"  # and then to merge "@ultralytics/run-ci-and-merge"
WORKFLOW_FILES = ["ci.yml", "docker.yml"]


def get_pr_branch(event) -> tuple[str, str | None]:
    """Gets the PR branch name, creating temp branch for forks, returning (branch, temp_branch_to_delete)."""
    pr_number = event.event_data["issue"]["number"]
    pr_data = event.get_repo_data(f"pulls/{pr_number}")
    head = pr_data.get("head", {})

    # Check if PR is from a fork
    is_fork = head.get("repo") and head["repo"]["id"] != pr_data["base"]["repo"]["id"]

    if is_fork:
        # Create temp branch in base repo for fork PRs
        temp_branch = f"temp-ci-{pr_number}-{int(time.time() * 1000)}"
        repo = event.repository
        event.post(
            f"{GITHUB_API_URL}/repos/{repo}/git/refs", json={"ref": f"refs/heads/{temp_branch}", "sha": head["sha"]}
        )
        return temp_branch, temp_branch

    return head.get("ref", "main"), None


def trigger_and_get_workflow_info(event, branch: str, temp_branch: str | None = None) -> list[dict]:
    """Triggers workflows and returns their information, deleting temp branch if provided."""
    repo = event.repository
    results = []

    try:
        # Trigger all workflows
        for file in WORKFLOW_FILES:
            event.post(f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{file}/dispatches", json={"ref": branch})

        # Wait for workflows to be created and start
        time.sleep(60)

        # Collect information about all workflows
        for file in WORKFLOW_FILES:
            # Get workflow name
            response = event.get(f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{file}")
            name = file.replace(".yml", "").title()
            if response.status_code == 200:
                name = response.json().get("name", name)

            # Get run information
            run_url = f"https://github.com/{repo}/actions/workflows/{file}"
            run_number = None

            runs_response = event.get(
                f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{file}/runs?branch={branch}&event=workflow_dispatch&per_page=1"
            )

            if runs_response.status_code == 200 and (runs := runs_response.json().get("workflow_runs", [])):
                run_url = runs[0].get("html_url", run_url)
                run_number = runs[0].get("run_number")

            results.append({"name": name, "file": file, "url": run_url, "run_number": run_number})
    finally:
        # Always delete temp branch even if workflow collection fails
        if temp_branch:
            event.delete(f"{GITHUB_API_URL}/repos/{repo}/git/refs/heads/{temp_branch}")

    return results


def update_comment(event, comment_body: str, triggered_actions: list[dict], branch: str):
    """Updates the comment with workflow information."""
    if not triggered_actions:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    summary = (
        f"\n\n## ⚡ Actions Trigger\n\n"
        f"<sub>Made with ❤️ by [Ultralytics Actions](https://www.ultralytics.com/actions)<sub>\n\n"
        f"GitHub Actions below triggered via workflow dispatch on this "
        f"PR branch `{branch}` at {timestamp} with `{RUN_CI_KEYWORD}` command:\n\n"
    )

    for action in triggered_actions:
        run_info = f" run {action['run_number']}" if action["run_number"] else ""
        summary += f"* ✅ [{action['name']}]({action['url']}): `{action['file']}`{run_info}\n"

    new_body = comment_body.replace(RUN_CI_KEYWORD, summary).strip()
    comment_id = event.event_data["comment"]["id"]
    event.patch(f"{GITHUB_API_URL}/repos/{event.repository}/issues/comments/{comment_id}", json={"body": new_body})


def main(*args, **kwargs):
    """Handles triggering workflows from PR comments."""
    event = Action(*args, **kwargs)

    # Only process new comments on PRs
    if (
        event.event_name != "issue_comment"
        or "pull_request" not in event.event_data.get("issue", {})
        or event.event_data.get("action") != "created"
    ):
        return

    # Get comment info
    comment_body = event.event_data["comment"].get("body") or ""
    username = event.event_data["comment"]["user"]["login"]

    # Check for keyword without surrounding backticks to avoid triggering on replies
    has_keyword = RUN_CI_KEYWORD in comment_body and comment_body.count(RUN_CI_KEYWORD) > comment_body.count(
        f"`{RUN_CI_KEYWORD}`"
    )
    if not has_keyword or not event.is_org_member(username):
        return

    # Get branch, trigger workflows, and update comment
    event.toggle_eyes_reaction(True)
    branch, temp_branch = get_pr_branch(event)
    print(f"Triggering workflows on branch: {branch}" + (" (temp)" if temp_branch else ""))

    triggered_actions = trigger_and_get_workflow_info(event, branch, temp_branch)
    update_comment(event, comment_body, triggered_actions, branch)
    event.toggle_eyes_reaction(False)


if __name__ == "__main__":
    main()
