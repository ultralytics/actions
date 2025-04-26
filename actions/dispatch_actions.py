# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import os
import time
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

    comment_id = comment.get("id")
    body = remove_html_comments(comment.get("body", ""))
    username = comment.get("user", {}).get("login")

    return comment_id, body, username


def get_pr_branch(event) -> str:
    """Gets the PR branch from issue comment or PR comment events."""
    # For issue comments on PRs
    if event.event_name == "issue_comment" and "pull_request" in event.event_data.get("issue", {}):
        pr_number = event.event_data["issue"]["number"]
        pr_data = event.get_repo_data(f"pulls/{pr_number}")
        return pr_data.get("head", {}).get("ref", "main")

    return "main"  # Default to main if not a PR


def get_recent_workflow_run(event, workflow_file: str, branch: str) -> str:
    """Gets the URL of the most recent workflow run for the specified workflow."""
    repo = event.repository

    # Wait a moment for the workflow to be created
    time.sleep(2)

    # Query for recent runs of this workflow
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/runs?branch={branch}&per_page=1"
    response = requests.get(url, headers=event.headers)

    if response.status_code == 200:
        data = response.json()
        workflow_runs = data.get("workflow_runs", [])
        if workflow_runs:
            # Get the HTML URL of the most recent run
            return workflow_runs[0].get("html_url")

    # Fallback to the general workflow URL if we can't get the specific run
    return f"https://github.com/{repo}/actions/workflows/{workflow_file}"


def trigger_workflows(event, branch) -> List[Dict]:
    """Triggers the predefined workflows on the specified branch."""
    results = []
    repo = event.repository

    for workflow_file in WORKFLOW_FILES:
        # Trigger the workflow
        url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
        response = requests.post(url, json={"ref": branch}, headers=event.headers)

        # Get the specific run URL if successful
        if response.status_code == 204:
            workflow_url = get_recent_workflow_run(event, workflow_file, branch)
            print(f"Found specific run URL: {workflow_url}")
        else:
            # Fallback to generic URL if the trigger failed
            workflow_url = f"https://github.com/{repo}/actions/workflows/{workflow_file}"

        workflow_name = workflow_file.replace(".yml", "").replace("-", " ").title()
        results.append({"name": workflow_name, "status": response.status_code, "url": workflow_url})

        print(f"{'Successful' if response.status_code == 204 else 'Failed'} workflow trigger: {workflow_name}")

    return results


def update_comment(event, comment_id: int, body: str, triggered_actions: List[Dict], branch: str) -> bool:
    """Updates the comment by replacing the trigger keyword with a summary."""
    if not triggered_actions:
        return False

    # Create the summary with branch info
    summary = f"Actions started by workflow dispatch on this PR `{branch}` branch:\n\n"
    for action in triggered_actions:
        status_emoji = "✅" if action["status"] == 204 else "⚠️"
        summary += f"* {status_emoji} [{action['name']}]({action['url']})\n"

    # Add footer
    summary += "\n<sub>Triggered by [Ultralytics Actions](https://www.ultralytics.com/actions)</sub>"

    # Replace the trigger keyword
    new_body = body.replace(TRIGGER_KEYWORD, summary)

    # Update the comment
    url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/comments/{comment_id}"
    response = requests.patch(url, json={"body": new_body}, headers=event.headers)

    return response.status_code == 200


def main(*args, **kwargs):
    """Handles triggering workflows from PR comments."""
    event = Action(*args, **kwargs)

    # Only process issue comments (comments on PRs are issue comments)
    if event.event_name != "issue_comment":
        print(f"Event {event.event_name} is not an issue comment, skipping.")
        return

    # Only process comments on PRs
    if "pull_request" not in event.event_data.get("issue", {}):
        print("Comment is not on a pull request, skipping.")
        return

    comment_id, body, username = get_comment_info(event)

    # Check for trigger keyword
    if TRIGGER_KEYWORD not in body:
        print(f"Trigger keyword '{TRIGGER_KEYWORD}' not found in the comment.")
        return

    # Check permissions
    if not event.is_org_member(username):
        print(f"User {username} is not a member of the organization and cannot trigger actions.")
        return

    # Get PR branch and trigger workflows
    branch = get_pr_branch(event)
    print(f"Triggering workflows on branch: {branch}")

    triggered_actions = trigger_workflows(event, branch)

    # Update the comment with results
    success = update_comment(event, comment_id, body, triggered_actions, branch)
    print(f"Comment update {'succeeded' if success else 'failed'}.")


if __name__ == "__main__":
    main()
