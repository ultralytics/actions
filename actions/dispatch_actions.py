# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import os
import time
from datetime import datetime
from typing import Dict, List, Tuple

import requests

from .utils import (
    GITHUB_API_URL,
    Action,
    remove_html_comments,
)

# The trigger keyword that will be detected in comments
TRIGGER_KEYWORD = os.getenv("TRIGGER_KEYWORD", "@ultralytics/dispatch-actions")

# List of workflow YAML files that can be triggered
WORKFLOW_FILES = ["ci.yml", "docker.yml"]


def get_comment_info(event) -> Tuple[int, str, str]:
    """Extracts comment ID, body text, and username from a comment event."""
    data = event.event_data
    comment = data.get("comment", {})

    return comment.get("id"), remove_html_comments(comment.get("body", "")), comment.get("user", {}).get("login")


def get_pr_branch(event) -> str:
    """Gets the PR branch from issue comment events."""
    if "pull_request" in event.event_data.get("issue", {}):
        pr_number = event.event_data["issue"]["number"]
        pr_data = event.get_repo_data(f"pulls/{pr_number}")
        return pr_data.get("head", {}).get("ref", "main")
    return "main"


def get_workflow_info(event, workflow_file: str) -> Dict:
    """Gets workflow name and other metadata."""
    repo = event.repository
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}"
    response = requests.get(url, headers=event.headers)

    if response.status_code == 200:
        workflow_data = response.json()
        return {"name": workflow_data.get("name", workflow_file.replace(".yml", "").title())}

    return {"name": workflow_file.replace(".yml", "").title()}


def get_workflow_run(event, workflow_file: str, branch: str) -> Dict:
    """Gets the most recent workflow run for the specified workflow."""
    repo = event.repository
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/runs?branch={branch}&event=workflow_dispatch&per_page=1"
    response = requests.get(url, headers=event.headers)

    if response.status_code == 200:
        runs = response.json().get("workflow_runs", [])
        if runs:
            return {"url": runs[0].get("html_url"), "run_number": runs[0].get("run_number")}

    return {"url": f"https://github.com/{repo}/actions/workflows/{workflow_file}", "run_number": None}


def trigger_workflows(event, branch: str) -> List[Dict]:
    """Triggers workflows and collects run information."""
    results = []
    repo = event.repository

    # First trigger all workflows
    for workflow_file in WORKFLOW_FILES:
        url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
        requests.post(url, json={"ref": branch}, headers=event.headers)

    # Wait for workflows to be created
    time.sleep(10)

    # Then collect information about all workflows
    for workflow_file in WORKFLOW_FILES:
        workflow_info = get_workflow_info(event, workflow_file)
        run_info = get_workflow_run(event, workflow_file, branch)

        results.append(
            {
                "name": workflow_info["name"],
                "file": workflow_file,
                "url": run_info["url"],
                "run_number": run_info["run_number"],
            }
        )

    return results


def update_comment(event, comment_id: int, body: str, triggered_actions: List[Dict], branch: str) -> bool:
    """Updates the comment with workflow information."""
    if not triggered_actions:
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    summary = (
        f"\n\n### ⚡ Actions Triggered\n\nGitHub Actions below triggered via workflow dispatch on this "
        f"PR branch `{branch}` at {timestamp} with `@ultralytics/dispatch-actions`:\n\n"
    )
    for action in triggered_actions:
        run_info = f"run {action['run_number']}" if action["run_number"] else ""
        summary += f"* ✅ [{action['name']}]({action['url']}): `{action['file']}`"
        if run_info:
            summary += f" {run_info}"
        summary += "\n"

    summary += "\n<sub>Made with ❤️ by [Ultralytics Actions](https://www.ultralytics.com/actions)<sub>\n\n"

    new_body = body.replace(TRIGGER_KEYWORD, summary).strip()
    url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/comments/{comment_id}"
    response = requests.patch(url, json={"body": new_body}, headers=event.headers)

    return response.status_code == 200


def main(*args, **kwargs):
    """Handles triggering workflows from PR comments."""
    event = Action(*args, **kwargs)

    # Only process comments on PRs
    if (
        event.event_name != "issue_comment"
        or "pull_request" not in event.event_data.get("issue", {})
        or event.event_data.get("action") != "created"
    ):
        print("Not a new PR comment, skipping.")
        return

    comment_id, body, username = get_comment_info(event)

    # Check for trigger keyword and permissions
    if TRIGGER_KEYWORD not in body:
        return
    if not event.is_org_member(username):
        print(f"User {username} cannot trigger actions.")
        return

    # Get branch and trigger workflows
    branch = get_pr_branch(event)
    print(f"Triggering workflows on branch: {branch}")

    triggered_actions = trigger_workflows(event, branch)

    # Update the comment
    success = update_comment(event, comment_id, body, triggered_actions, branch)
    print(f"Comment update {'succeeded' if success else 'failed'}.")


if __name__ == "__main__":
    main()
