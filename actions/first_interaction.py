# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import os
from typing import Dict, List, Tuple

import requests

from .utils import (
    GITHUB_API_URL,
    Action,
    get_completion,
    remove_html_comments,
)

# Environment variables
BLOCK_USER = os.getenv("BLOCK_USER", "false").lower() == "true"


def get_event_content(event) -> Tuple[int, str, str, str, str, str, str]:
    """Extracts key information from GitHub event data for issues, pull requests, or discussions."""
    data = event.event_data
    name = event.event_name
    action = data["action"]  # 'opened', 'closed', 'created' (discussion), etc.
    if name == "issues":
        item = data["issue"]
        issue_type = "issue"
    elif name in ["pull_request", "pull_request_target"]:
        pr_number = data["pull_request"]["number"]
        item = event.get_repo_data(f"pulls/{pr_number}")
        issue_type = "pull request"
    elif name == "discussion":
        item = data["discussion"]
        issue_type = "discussion"
    else:
        raise ValueError(f"Unsupported event type: {name}")

    number = item["number"]
    node_id = item.get("node_id") or item.get("id")
    title = item["title"]
    body = remove_html_comments(item.get("body", ""))
    username = item["user"]["login"]
    return number, node_id, title, body, username, issue_type, action


def update_issue_pr_content(event, number: int, node_id: str, issue_type: str):
    """Updates the title and body of an issue, pull request, or discussion with predefined content."""
    new_title = "Content Under Review"
    new_body = """This post has been flagged for review by [Ultralytics Actions](https://ultralytics.com/actions) due to possible spam, abuse, or off-topic content. For more information please see our:

- [Code of Conduct](https://docs.ultralytics.com/help/code_of_conduct)
- [Security Policy](https://docs.ultralytics.com/help/security)

For questions or bug reports related to this action please visit https://github.com/ultralytics/actions.

Thank you 🙏
"""
    if issue_type == "discussion":
        mutation = """
mutation($discussionId: ID!, $title: String!, $body: String!) {
    updateDiscussion(input: {discussionId: $discussionId, title: $title, body: $body}) {
        discussion {
            id
        }
    }
}
"""
        event.graphql_request(mutation, variables={"discussionId": node_id, "title": new_title, "body": new_body})
    else:
        url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}"
        r = requests.patch(url, json={"title": new_title, "body": new_body}, headers=event.headers)
        print(f"{'Successful' if r.status_code == 200 else 'Fail'} issue/PR #{number} update: {r.status_code}")


def close_issue_pr(event, number: int, node_id: str, issue_type: str):
    """Closes the specified issue, pull request, or discussion using the GitHub API."""
    if issue_type == "discussion":
        mutation = """
mutation($discussionId: ID!) {
    closeDiscussion(input: {discussionId: $discussionId}) {
        discussion {
            id
        }
    }
}
"""
        event.graphql_request(mutation, variables={"discussionId": node_id})
    else:
        url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}"
        r = requests.patch(url, json={"state": "closed"}, headers=event.headers)
        print(f"{'Successful' if r.status_code == 200 else 'Fail'} issue/PR #{number} close: {r.status_code}")


def lock_issue_pr(event, number: int, node_id: str, issue_type: str):
    """Locks an issue, pull request, or discussion to prevent further interactions."""
    if issue_type == "discussion":
        mutation = """
mutation($lockableId: ID!, $lockReason: LockReason) {
    lockLockable(input: {lockableId: $lockableId, lockReason: $lockReason}) {
        lockedRecord {
            ... on Discussion {
                id
            }
        }
    }
}
"""
        event.graphql_request(mutation, variables={"lockableId": node_id, "lockReason": "OFF_TOPIC"})
    else:
        url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/lock"
        r = requests.put(url, json={"lock_reason": "off-topic"}, headers=event.headers)
        print(f"{'Successful' if r.status_code in {200, 204} else 'Fail'} issue/PR #{number} lock: {r.status_code}")


def block_user(event, username: str):
    """Blocks a user from the organization using the GitHub API."""
    url = f"{GITHUB_API_URL}/orgs/{event.repository.split('/')[0]}/blocks/{username}"
    r = requests.put(url, headers=event.headers)
    print(f"{'Successful' if r.status_code == 204 else 'Fail'} user block for {username}: {r.status_code}")


def get_relevant_labels(
    issue_type: str, title: str, body: str, available_labels: Dict, current_labels: List
) -> List[str]:
    """Determines relevant labels for GitHub issues/PRs using OpenAI, considering title, body, and existing labels."""
    # Remove mutually exclusive labels like both 'bug' and 'question' or inappropriate labels like 'help wanted'
    for label in ["help wanted", "TODO"]:  # normal case
        available_labels.pop(label, None)  # remove as should only be manually added
    if "bug" in current_labels:
        available_labels.pop("question", None)
    elif "question" in current_labels:
        available_labels.pop("bug", None)

    # Add "Alert" to available labels if not present
    if "Alert" not in available_labels:
        available_labels["Alert"] = (
            "Potential spam, abuse, or illegal activity including advertising, unsolicited promotions, malware, phishing, crypto offers, pirated software or media, free movie downloads, cracks, keygens or any other content that violates terms of service or legal standards."
        )

    labels = "\n".join(f"- {name}: {description}" for name, description in available_labels.items())

    prompt = f"""Select the top 1-3 most relevant labels for the following GitHub {issue_type}.

INSTRUCTIONS:
1. Review the {issue_type} title and description.
2. Consider the available labels and their descriptions.
3. Choose 1-3 labels that best match the {issue_type} content.
4. Only use the "Alert" label when you have high confidence that this is an inappropriate {issue_type}.
5. Respond ONLY with the chosen label names (no descriptions), separated by commas.
6. If no labels are relevant, respond with 'None'.

AVAILABLE LABELS:
{labels}

{issue_type.upper()} TITLE:
{title}

{issue_type.upper()} DESCRIPTION:
{body[:16000]}

YOUR RESPONSE (label names only):
"""
    print(prompt)  # for short-term debugging
    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant that labels GitHub issues, PRs, and discussions.",
        },
        {"role": "user", "content": prompt},
    ]
    suggested_labels = get_completion(messages)
    if "none" in suggested_labels.lower():
        return []

    available_labels_lower = {name.lower(): name for name in available_labels}
    return [
        available_labels_lower[label.lower().strip()]
        for label in suggested_labels.split(",")
        if label.lower().strip() in available_labels_lower
    ]


def get_label_ids(event, labels: List[str]) -> List[str]:
    """Retrieves GitHub label IDs for a list of label names using the GraphQL API."""
    query = """
query($owner: String!, $name: String!) {
    repository(owner: $owner, name: $name) {
        labels(first: 100, query: "") {
            nodes {
                id
                name
            }
        }
    }
}
"""
    owner, repo = event.repository.split("/")
    result = event.graphql_request(query, variables={"owner": owner, "name": repo})
    if "data" in result and "repository" in result["data"]:
        all_labels = result["data"]["repository"]["labels"]["nodes"]
        label_map = {label["name"].lower(): label["id"] for label in all_labels}
        return [label_map.get(label.lower()) for label in labels if label.lower() in label_map]
    else:
        print(f"Failed to fetch labels: {result.get('errors', 'Unknown error')}")
        return []


def apply_labels(event, number: int, node_id: str, labels: List[str], issue_type: str):
    """Applies specified labels to a GitHub issue, pull request, or discussion using the appropriate API."""
    if "Alert" in labels:
        create_alert_label(event)

    if issue_type == "discussion":
        print(f"Using node_id: {node_id}")  # Debug print
        label_ids = get_label_ids(event, labels)
        if not label_ids:
            print("No valid labels to apply.")
            return

        mutation = """
mutation($labelableId: ID!, $labelIds: [ID!]!) {
    addLabelsToLabelable(input: {labelableId: $labelableId, labelIds: $labelIds}) {
        labelable {
            ... on Discussion {
                id
            }
        }
    }
}
"""
        event.graphql_request(mutation, {"labelableId": node_id, "labelIds": label_ids})
        print(f"Successfully applied labels: {', '.join(labels)}")
    else:
        url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/labels"
        r = requests.post(url, json={"labels": labels}, headers=event.headers)
        print(f"{'Successful' if r.status_code == 200 else 'Fail'} apply labels {', '.join(labels)}: {r.status_code}")


def create_alert_label(event):
    """Creates the 'Alert' label in the repository if it doesn't exist, with a red color and description."""
    alert_label = {"name": "Alert", "color": "FF0000", "description": "Potential spam, abuse, or off-topic."}
    requests.post(f"{GITHUB_API_URL}/repos/{event.repository}/labels", json=alert_label, headers=event.headers)


def is_org_member(event, username: str) -> bool:
    """Checks if a user is a member of the organization using the GitHub API."""
    org_name = event.repository.split("/")[0]
    url = f"{GITHUB_API_URL}/orgs/{org_name}/members/{username}"
    r = requests.get(url, headers=event.headers)
    return r.status_code == 204  # 204 means the user is a member


def add_comment(event, number: int, node_id: str, comment: str, issue_type: str):
    """Adds a comment to the specified issue, pull request, or discussion using the GitHub API."""
    if issue_type == "discussion":
        mutation = """
mutation($discussionId: ID!, $body: String!) {
    addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
        comment {
            id
        }
    }
}
"""
        event.graphql_request(mutation, variables={"discussionId": node_id, "body": comment})
    else:
        url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/comments"
        r = requests.post(url, json={"body": comment}, headers=event.headers)
        print(f"{'Successful' if r.status_code in {200, 201} else 'Fail'} issue/PR #{number} comment: {r.status_code}")


def get_first_interaction_response(event, issue_type: str, title: str, body: str, username: str) -> str:
    """Generates a custom LLM response for GitHub issues, PRs, or discussions based on content."""
    issue_discussion_response = f"""
👋 Hello @{username}, thank you for submitting a `{event.repository}` 🚀 {issue_type.capitalize()}. To help us address your concern efficiently, please ensure you've provided the following information:

1. For bug reports:
   - A clear and concise description of the bug
   - A minimum reproducible example (MRE)[https://docs.ultralytics.com/help/minimum_reproducible_example/] that demonstrates the issue
   - Your environment details (OS, Python version, package versions)
   - Expected behavior vs. actual behavior
   - Any error messages or logs related to the issue

2. For feature requests:
   - A clear and concise description of the proposed feature
   - The problem this feature would solve
   - Any alternative solutions you've considered

3. For questions:
   - Provide as much context as possible about your question
   - Include any research you've already done on the topic
   - Specify which parts of the [documentation](https://docs.ultralytics.com), if any, you've already consulted

Please make sure you've searched existing {issue_type}s to avoid duplicates. If you need to add any additional information, please comment on this {issue_type}.

Thank you for your contribution to improving our project!
"""

    pr_response = f"""
👋 Hello @{username}, thank you for submitting an `{event.repository}` 🚀 PR! To ensure a seamless integration of your work, please review the following checklist:

- ✅ **Define a Purpose**: Clearly explain the purpose of your fix or feature in your PR description, and link to any [relevant issues](https://github.com/{event.repository}/issues). Ensure your commit messages are clear, concise, and adhere to the project's conventions.
- ✅ **Synchronize with Source**: Confirm your PR is synchronized with the `{event.repository}` `main` branch. If it's behind, update it by clicking the 'Update branch' button or by running `git pull` and `git merge main` locally.
- ✅ **Ensure CI Checks Pass**: Verify all Ultralytics [Continuous Integration (CI)](https://docs.ultralytics.com/help/CI/) checks are passing. If any checks fail, please address the issues.
- ✅ **Update Documentation**: Update the relevant [documentation](https://docs.ultralytics.com) for any new or modified features.
- ✅ **Add Tests**: If applicable, include or update tests to cover your changes, and confirm that all tests are passing.
- ✅ **Sign the CLA**: Please ensure you have signed our [Contributor License Agreement](https://docs.ultralytics.com/help/CLA/) if this is your first Ultralytics PR by writing "I have read the CLA Document and I sign the CLA" in a new message.
- ✅ **Minimize Changes**: Limit your changes to the **minimum** necessary for your bug fix or feature addition. _"It is not daily increase but daily decrease, hack away the unessential. The closer to the source, the less wastage there is."_  — Bruce Lee

For more guidance, please refer to our [Contributing Guide](https://docs.ultralytics.com/help/contributing). Don’t hesitate to leave a comment if you have any questions. Thank you for contributing to Ultralytics! 🚀
"""

    if issue_type == "pull request":
        example = os.getenv("FIRST_PR_RESPONSE") or pr_response
    else:
        example = os.getenv("FIRST_ISSUE_RESPONSE") or issue_discussion_response

    org_name, repo_name = event.repository.split("/")
    repo_url = f"https://github.com/{event.repository}"
    diff = event.get_pr_diff()[:32000] if issue_type == "pull request" else ""

    prompt = f"""Generate a customized response to the new GitHub {issue_type} below:

CONTEXT:
- Repository: {repo_name}
- Organization: {org_name}
- Repository URL: {repo_url}
- User: {username}

INSTRUCTIONS:
- Do not answer the question or resolve the issue directly
- Adapt the example {issue_type} response below as appropriate, keeping all badges, links and references provided
- For bug reports, specifically request a minimum reproducible example (MRE) if not provided
- INCLUDE ALL LINKS AND INSTRUCTIONS IN THE EXAMPLE BELOW, customized as appropriate
- Mention to the user that this is an automated response and that an Ultralytics engineer will also assist soon
- Do not add a sign-off or valediction like "best regards" at the end of your response
- Do not add spaces between bullet points or numbered lists
- Only link to files or URLs in the example below, do not add external links
- Use a few emojis to enliven your response

EXAMPLE {issue_type.upper()} RESPONSE:
{example}

{issue_type.upper()} TITLE:
{title}

{issue_type.upper()} DESCRIPTION:
{body[:16000]}

{"PULL REQUEST DIFF:" if issue_type == "pull request" else ""}
{diff if issue_type == "pull request" else ""}

YOUR {issue_type.upper()} RESPONSE:
"""
    print(f"\n\n{prompt}\n\n")  # for debug
    messages = [
        {
            "role": "system",
            "content": f"You are an Ultralytics AI assistant responding to GitHub {issue_type}s for {org_name}.",
        },
        {"role": "user", "content": prompt},
    ]
    return get_completion(messages)


def main(*args, **kwargs):
    """Executes auto-labeling and custom response generation for new GitHub issues, PRs, and discussions."""
    event = Action(*args, **kwargs)
    number, node_id, title, body, username, issue_type, action = get_event_content(event)
    available_labels = event.get_repo_data("labels")
    label_descriptions = {label["name"]: label.get("description", "") for label in available_labels}
    if issue_type == "discussion":
        current_labels = []  # For discussions, labels may need to be fetched differently or adjusted
    else:
        current_labels = [label["name"].lower() for label in event.get_repo_data(f"issues/{number}/labels")]
    relevant_labels = get_relevant_labels(issue_type, title, body, label_descriptions, current_labels)

    if relevant_labels:
        apply_labels(event, number, node_id, relevant_labels, issue_type)
        if "Alert" in relevant_labels and not is_org_member(event, username):
            update_issue_pr_content(event, number, node_id, issue_type)
            if issue_type != "pull request":
                close_issue_pr(event, number, node_id, issue_type)
            lock_issue_pr(event, number, node_id, issue_type)
            if BLOCK_USER:
                block_user(event, username=username)
    else:
        print("No relevant labels found or applied.")

    if action in {"opened", "created"}:
        custom_response = get_first_interaction_response(event, issue_type, title, body, username)
        add_comment(event, number, node_id, custom_response, issue_type)


if __name__ == "__main__":
    main()
