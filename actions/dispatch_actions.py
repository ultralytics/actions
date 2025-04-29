# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import time
from datetime import datetime
from typing import Dict, List

from .utils import GITHUB_API_URL, Action

# Configuration
RUN_CI_KEYWORD = "@ultralytics/run-ci"  # and then to merge "@ultralytics/run-ci-and-merge"
WORKFLOW_FILES = ["ci.yml", "docker.yml"]


def get_pr_branch(event) -> str:
    """Gets the PR branch name."""
    pr_number = event.event_data["issue"]["number"]
    pr_data = event.get_repo_data(f"pulls/{pr_number}")
    return pr_data.get("head", {}).get("ref", "main")


def trigger_and_get_workflow_info(event, branch: str) -> List[Dict]:
    """Triggers workflows and returns their information."""
    repo = event.repository
    results = []

    # Trigger all workflows
    for file in WORKFLOW_FILES:
        event.post(f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{file}/dispatches", json={"ref": branch})

    # Wait for workflows to be created
    time.sleep(10)

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
            f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{file}/runs?branch={branch}&event=workflow_dispatch&per_page=1",
        )

        if runs_response.status_code == 200:
            runs = runs_response.json().get("workflow_runs", [])
            if runs:
                run_url = runs[0].get("html_url", run_url)
                run_number = runs[0].get("run_number")

        results.append({"name": name, "file": file, "url": run_url, "run_number": run_number})

    return results


def update_comment(event, comment_body: str, triggered_actions: List[Dict], branch: str) -> bool:
    """Updates the comment with workflow information."""
    if not triggered_actions:
        return False

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
    comment_body = event.event_data["comment"].get("body", "")
    username = event.event_data["comment"]["user"]["login"]

    # Check for keyword without surrounding backticks to avoid triggering on replies
    has_keyword = RUN_CI_KEYWORD in comment_body and comment_body.count(RUN_CI_KEYWORD) > comment_body.count(
        f"`{RUN_CI_KEYWORD}`"
    )
    if not has_keyword or not event.is_org_member(username):
        return

    # Get branch, trigger workflows, and update comment
    event.toggle_eyes_reaction(True)
    branch = get_pr_branch(event)
    print(f"Triggering workflows on branch: {branch}")

    triggered_actions = trigger_and_get_workflow_info(event, branch)
    update_comment(event, comment_body, triggered_actions, branch)
    event.toggle_eyes_reaction(False)


if __name__ == "__main__":
    main()
