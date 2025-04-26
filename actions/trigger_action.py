# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import re
from typing import Dict, List, Tuple

import requests

from .utils import GITHUB_API_URL,Action,remove_html_comments

# The trigger keyword that will be detected in comments
TRIGGER_KEYWORD = "/run-actions"

# List of workflow files and display names
DEFAULT_ACTIONS = [
    {"workflow": "ci.yml", "name": "CI Slow Tests"},
    {"workflow": "docker.yml", "name": "Docker Build and Test"},
]


def is_org_member(event, username: str) -> bool:
    """Checks if a user is a member of the organization using the GitHub API."""
    org_name = event.repository.split("/")[0]
    url = f"{GITHUB_API_URL}/orgs/{org_name}/members/{username}"
    r = requests.get(url, headers=event.headers)
    return r.status_code == 204  # 204 means the user is a member


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


def trigger_workflows(event, actions_to_trigger: List[str]) -> List[Dict]:
    """Triggers the specified workflows via repository_dispatch event."""
    results = []
    repo = event.repository

    for action in actions_to_trigger:
        action_info = DEFAULT_ACTIONS.get(action, {})
        if not action_info:
            continue

        workflow_file = action_info.get("workflow")
        display_name = action_info.get("name")

        # Trigger the workflow using repository_dispatch
        url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
        payload = {
            "ref": "main",
            "inputs": {
                "triggered_by": f"comment-{event.event_data.get('comment', {}).get('id')}",
                "comment_url": event.event_data.get("comment", {}).get("html_url", ""),
            },
        }

        response = requests.post(url, json=payload, headers=event.headers)

        # Get the workflow run URL
        runs_url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/runs"
        runs_response = requests.get(runs_url, headers=event.headers)
        workflow_url = ""

        if runs_response.status_code == 200:
            runs = runs_response.json().get("workflow_runs", [])
            if runs:
                # Get the most recent run as it's likely the one we just triggered
                workflow_url = runs[0].get("html_url", "")

        results.append(
            {
                "action": action,
                "name": display_name,
                "workflow": workflow_file,
                "status": response.status_code,
                "url": workflow_url or f"https://github.com/{repo}/actions/workflows/{workflow_file}",
            }
        )

    return results


def replace_trigger_keyword(event, comment_id: int, body: str, triggered_actions: List[Dict]) -> bool:
    """Replaces the trigger keyword in the comment with a summary of triggered actions."""
    if not triggered_actions:
        return False

    # Create the replacement text
    summary = "### Actions Triggered\n\n"
    for action in triggered_actions:
        summary += f"* [{action['name']}]({action['url']})\n"

    # Replace the trigger keyword with the summary
    new_body = re.sub(
        pattern=f"{TRIGGER_KEYWORD}(\\s+[\\w,]+)?",  # Match the keyword and optional action list
        repl=summary,
        string=body,
    )

    # Update the comment with the new body
    url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/comments/{comment_id}"
    response = requests.patch(url, json={"body": new_body}, headers=event.headers)

    return response.status_code == 200


def parse_actions_to_trigger(body: str) -> List[str]:
    """Parses the actions to trigger from the comment body."""
    # Look for the trigger keyword followed by optional action identifiers
    match = re.search(f"{TRIGGER_KEYWORD}\\s+([\\w,]+)", body)

    if match:
        # Parse the comma-separated list of actions
        actions_str = match.group(1)
        return [action.strip() for action in actions_str.split(",") if action.strip() in DEFAULT_ACTIONS]

    # If no specific actions provided, return all available actions
    return list(DEFAULT_ACTIONS.keys())


def main(*args, **kwargs):
    """Detects trigger keywords in comments and starts corresponding workflows."""
    event = Action(*args, **kwargs)
    comment_id, body, username, context_type = get_comment_content(event)

    # Check if the trigger keyword is in the comment
    if TRIGGER_KEYWORD not in body:
        print(f"Trigger keyword '{TRIGGER_KEYWORD}' not found in the comment.")
        return

    # Only org members can trigger actions
    if not is_org_member(event, username):
        print(f"User {username} is not a member of the organization and cannot trigger actions.")
        return

    # Parse which actions to trigger
    actions_to_trigger = parse_actions_to_trigger(body)
    print(f"Actions to trigger: {actions_to_trigger}")

    # Trigger the workflows
    triggered_actions = trigger_workflows(event, actions_to_trigger)
    print(f"Triggered actions: {triggered_actions}")

    # Replace the trigger keyword with a summary
    success = replace_trigger_keyword(event, comment_id, body, triggered_actions)
    print(f"Comment update {'succeeded' if success else 'failed'}.")


if __name__ == "__main__":
    main()
