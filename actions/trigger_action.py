# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import os
import re
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


def get_comment_content(event) -> Tuple[int, str, str, str]:
    """Extracts key information from GitHub event data for issue and PR comments."""
    data = event.event_data
    comment = data.get("comment", {})
    issue = data.get("issue", {})
    pr = issue.get("pull_request", {})

    comment_id = comment.get("id")
    body = remove_html_comments(comment.get("body", ""))
    username = comment.get("user", {}).get("login")
    context_type = "pull_request" if pr else "issue"

    return comment_id, body, username, context_type


def trigger_workflows(event) -> List[Dict]:
    """Triggers the predefined workflows via repository_dispatch event."""
    results = []
    repo = event.repository

    # Determine which branch to run the workflows on
    ref = None
    if event.event_name == "pull_request_review_comment":
        # This is a PR comment
        ref = event.pr.get("head", {}).get("ref")
    elif event.event_name == "issue_comment" and "pull_request" in event.event_data.get("issue", {}):
        # This is a comment on an issue that is a PR
        pr_number = event.event_data["issue"]["number"]
        pr_data = event.get_repo_data(f"pulls/{pr_number}")
        ref = pr_data.get("head", {}).get("ref")
    if not ref:
        ref = "main"

    for workflow_file in WORKFLOW_FILES:
        # Trigger the workflow using repository_dispatch
        url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
        payload = {
            "ref": ref,
            "inputs": {
                "triggered_by": f"comment-{event.event_data.get('comment', {}).get('id')}",
                "comment_url": event.event_data.get("comment", {}).get("html_url", ""),
            },
        }

        response = requests.post(url, json=payload, headers=event.headers)
        status_code = response.status_code

        # Get the workflow name from the filename
        workflow_name = workflow_file.replace(".yml", "").replace("-", " ").title()

        # Create the workflow URL for GitHub Actions UI
        workflow_url = f"https://github.com/{repo}/actions/workflows/{workflow_file}"

        results.append({"name": workflow_name, "status": status_code, "url": workflow_url, "ref": ref})

        print(
            f"{'Successful' if status_code == 204 else 'Failed'} workflow trigger for {workflow_name} on branch '{ref}': {status_code}"
        )

    return results


def replace_trigger_keyword(event, comment_id: int, body: str, triggered_actions: List[Dict]) -> bool:
    """Replaces the trigger keyword in the comment with a summary of triggered actions."""
    if not triggered_actions:
        return False

    # Get the branch name from the first action (all use the same branch)
    branch = triggered_actions[0].get("ref", "main")

    # Create the replacement text with emoji and clear formatting
    summary = f"### 🚀 Actions Triggered on `{branch}`\n\n"
    for action in triggered_actions:
        status_emoji = "✅" if action["status"] == 204 else "⚠️"
        summary += f"* {status_emoji} [{action['name']}]({action['url']})\n"

    # Add a footer note
    repo_parts = event.repository.split("/")
    summary += f"\n<sub>Triggered by [Ultralytics Actions](https://github.com/{repo_parts[0]}/actions)</sub>"

    # Replace the trigger keyword with the summary
    new_body = body.replace(TRIGGER_KEYWORD, summary)

    # Update the comment with the new body
    url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/comments/{comment_id}"
    response = requests.patch(url, json={"body": new_body}, headers=event.headers)
    status_code = response.status_code

    print(f"{'Successful' if status_code == 200 else 'Failed'} comment update: {status_code}")
    return status_code == 200


def parse_actions_to_trigger(body: str) -> List[str]:
    """Parses the workflow yaml files to trigger from the comment body."""
    # Look for the trigger keyword followed by a space and a list of workflows
    match = re.search(f"{TRIGGER_KEYWORD}\\s+([\\w\\.,\\-]+\\.ya?ml(?:[\\s,]+[\\w\\.,\\-]+\\.ya?ml)*)", body)

    if match:
        # Parse the comma or space-separated list of workflow files
        actions_str = match.group(1)
        return [
            action.strip() for action in re.split(r"[,\s]+", actions_str) if action.strip().endswith((".yml", ".yaml"))
        ]

    return []  # No workflows specified


def main(*args, **kwargs):
    """Detects trigger keywords in comments and starts predefined workflows."""
    event = Action(*args, **kwargs)

    # Only process comment events
    if event.event_name not in ["issue_comment", "pull_request_review_comment"]:
        print(f"Event {event.event_name} is not a comment event, skipping.")
        return

    comment_id, body, username, context_type = get_comment_content(event)

    # Check if the trigger keyword is in the comment
    if TRIGGER_KEYWORD not in body:
        print(f"Trigger keyword '{TRIGGER_KEYWORD}' not found in the comment.")
        return

    # Only org members can trigger actions
    if not event.is_org_member(username):
        print(f"User {username} is not a member of the organization and cannot trigger actions.")
        return

    print(f"Triggering workflows: {WORKFLOW_FILES}")

    # Trigger the workflows
    triggered_actions = trigger_workflows(event)
    print(f"Triggered workflows: {triggered_actions}")

    # Replace the trigger keyword with a summary
    success = replace_trigger_keyword(event, comment_id, body, triggered_actions)
    print(f"Comment update {'succeeded' if success else 'failed'}.")


if __name__ == "__main__":
    main()
