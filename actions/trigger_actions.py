# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import os
from typing import Dict, List, Tuple

import requests

from .utils import (
    GITHUB_API_URL,
    Action,
    remove_html_comments,
)

# The trigger keyword that will be detected in comments
TRIGGER_KEYWORD = os.getenv("TRIGGER_KEYWORD", "/actions")

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


def trigger_workflows(event, branch) -> List[Dict]:
    """Triggers the predefined workflows on the specified branch."""
    results = []
    repo = event.repository

    for workflow_file in WORKFLOW_FILES:
        url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
        payload = {
            "ref": branch,
            "inputs": {
                "triggered_by": f"comment-{event.event_data.get('comment', {}).get('id')}",
                "comment_url": event.event_data.get("comment", {}).get("html_url", ""),
            },
        }

        response = requests.post(url, json=payload, headers=event.headers)
        status_code = response.status_code

        # Get workflow name and URL
        workflow_name = workflow_file.replace(".yml", "").replace("-", " ").title()
        workflow_url = f"https://github.com/{repo}/actions/workflows/{workflow_file}"

        results.append({"name": workflow_name, "status": status_code, "url": workflow_url})

        print(f"{'Successful' if status_code == 204 else 'Failed'} workflow trigger: {workflow_name}")

    return results


def update_comment(event, comment_id: int, body: str, triggered_actions: List[Dict], branch: str) -> bool:
    """Updates the comment by replacing the trigger keyword with a summary."""
    if not triggered_actions:
        return False

    # Create the summary with branch info
    summary = f"### 🚀 Actions Triggered on `{branch}`\n\n"
    for action in triggered_actions:
        status_emoji = "✅" if action["status"] == 204 else "⚠️"
        summary += f"* {status_emoji} [{action['name']}]({action['url']})\n"

    # Add footer
    repo_parts = event.repository.split("/")
    summary += f"\n<sub>Triggered by [Ultralytics Actions](https://www.ultralytics.com/actions)</sub>"

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
