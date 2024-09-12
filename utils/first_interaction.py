# Ultralytics YOLO 🚀, AGPL-3.0 License https://ultralytics.com/license

import json
import os
import re
from typing import Dict, List, Tuple

import requests

# Environment variables
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
BLOCK_USER = os.getenv("BLOCK_USER", "false").lower() == "true"

# OpenAI settings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # update as required
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_API_KEY = os.getenv("OPENAI_AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("OPENAI_AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("OPENAI_AZURE_API_VERSION", "2024-05-01-preview")  # update as required

DEFAULT_ISSUE_INSTRUCTIONS = """
Thank you for submitting an issue! To help us address your concern efficiently, please ensure you've provided the following information:

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
   - Specify which parts of the [documentation](https://docs.ultralytics.com/), if any, you've already consulted

Please make sure you've searched existing issues to avoid duplicates. If you need to add any additional information, please comment on this issue.

Thank you for your contribution to improving our project!
"""

DEFAULT_PR_INSTRUCTIONS = f"""
👋 Hello @${{ github.actor }}, thank you for submitting an Ultralytics 🚀 PR! To ensure a seamless integration of your work, please review the following checklist:

- ✅ **Define a Purpose**: Clearly explain the purpose of your fix or feature in your PR description, and link to any [relevant issues](https://github.com/{REPO_NAME}/issues). Ensure your commit messages are clear, concise, and adhere to the project's conventions.
- ✅ **Stay Up-to-Date**: Confirm your PR is synchronized with the `{REPO_NAME}` `main` branch. If it's behind, update it by clicking the 'Update branch' button or by running `git pull` and `git merge main` locally.
- ✅ **Ensure CI Checks Pass**: Verify all Ultralytics [Continuous Integration (CI)](https://docs.ultralytics.com/help/CI/) checks are passing. If any checks fail, please address the issues.
- ✅ **Update Documentation**: Update the relevant [documentation](https://docs.ultralytics.com) for any new or modified features.
- ✅ **Add Tests**: If applicable, include or update tests to cover your changes, and confirm that all tests are passing.
- ✅ **Sign the CLA**: Please ensure you have signed our [Contributor License Agreement](https://docs.ultralytics.com/help/CLA/) if this is your first Ultralytics PR by writing "I have read the CLA Document and I sign the CLA" in a new message.
- ✅ **Minimize Changes**: Limit your changes to the **minimum** necessary for your bug fix or feature addition. _"It is not daily increase but daily decrease, hack away the unessential. The closer to the source, the less wastage there is."_  — Bruce Lee

For more guidance, please refer to our [Contributing Guide](https://docs.ultralytics.com/help/contributing). Don’t hesitate to leave a comment if you have any questions. Thank you for contributing to Ultralytics! 🚀
"""

FIRST_INTERACTION_ISSUE_INSTRUCTIONS = os.getenv("FIRST_INTERACTION_ISSUE_INSTRUCTIONS", DEFAULT_ISSUE_INSTRUCTIONS)
FIRST_INTERACTION_PR_INSTRUCTIONS = os.getenv("FIRST_INTERACTION_PR_INSTRUCTIONS", DEFAULT_PR_INSTRUCTIONS)


def remove_html_comments(body: str) -> str:
    """Removes HTML comment blocks from the body text."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()


def get_completion(messages: list) -> str:
    """Get completion from OpenAI or Azure OpenAI."""
    if AZURE_API_KEY and AZURE_ENDPOINT:
        url = f"{AZURE_ENDPOINT}/openai/deployments/{OPENAI_MODEL}/chat/completions?api-version={AZURE_API_VERSION}"
        headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
        data = {"messages": messages}
    else:
        assert OPENAI_API_KEY, "OpenAI API key is required."
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        data = {"model": OPENAI_MODEL, "messages": messages}

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def get_pr_diff(pr_number):
    """Fetches the diff of a specific PR from a GitHub repository."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/pulls/{pr_number}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else ""


def get_github_data(endpoint: str) -> dict:
    """Generic function to fetch data from GitHub API."""
    response = requests.get(f"{GITHUB_API_URL}/repos/{REPO_NAME}/{endpoint}", headers=GITHUB_HEADERS)
    response.raise_for_status()
    return response.json()


def get_event_content() -> Tuple[int, str, str, str]:
    """Extracts the number, title, body, and username from the issue or pull request."""
    with open(GITHUB_EVENT_PATH) as f:
        event_data = json.load(f)

    if GITHUB_EVENT_NAME == "issues":
        item = event_data["issue"]
    elif GITHUB_EVENT_NAME in ["pull_request", "pull_request_target"]:
        pr_number = event_data["pull_request"]["number"]
        item = get_github_data(f"pulls/{pr_number}")
    else:
        raise ValueError(f"Unsupported event type: {GITHUB_EVENT_NAME}")

    body = remove_html_comments(item.get("body", ""))
    return item["number"], item["title"], body, item["user"]["login"]


def update_issue_pr_content(number: int):
    """Updates the title and body of the issue or pull request."""
    new_title = "Content Under Review"
    new_body = """This post has been flagged for review by [Ultralytics Actions](https://ultralytics.com/actions) due to possible spam, abuse, or off-topic content. For more information please see our:

- [Code of Conduct](https://docs.ultralytics.com/help/code_of_conduct)
- [Security Policy](https://docs.ultralytics.com/help/security)

For questions or bug reports related to this action please visit https://github.com/ultralytics/actions.

Thank you 🙏
"""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/issues/{number}"
    data = {"title": new_title, "body": new_body}
    response = requests.patch(url, json=data, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        print(f"Successfully updated issue/PR #{number} title and body.")
    else:
        print(f"Failed to update issue/PR. Status code: {response.status_code}")


def close_issue_pr(number: int):
    """Closes the issue or pull request."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/issues/{number}"
    data = {"state": "closed"}
    response = requests.patch(url, json=data, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        print(f"Successfully closed issue/PR #{number}.")
    else:
        print(f"Failed to close issue/PR. Status code: {response.status_code}")


def lock_issue_pr(number: int):
    """Locks the issue or pull request."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/issues/{number}/lock"
    data = {"lock_reason": "off-topic"}
    response = requests.put(url, json=data, headers=GITHUB_HEADERS)
    if response.status_code == 204:
        print(f"Successfully locked issue/PR #{number}.")
    else:
        print(f"Failed to lock issue/PR. Status code: {response.status_code}")


def block_user(username: str):
    """Blocks a user from the organization."""
    url = f"{GITHUB_API_URL}/orgs/{REPO_NAME.split('/')[0]}/blocks/{username}"
    response = requests.put(url, headers=GITHUB_HEADERS)
    if response.status_code == 204:
        print(f"Successfully blocked user: {username}.")
    else:
        print(f"Failed to block user. Status code: {response.status_code}")


def get_relevant_labels(title: str, body: str, available_labels: Dict, current_labels: List) -> List[str]:
    """Uses OpenAI to determine the most relevant labels."""
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

    prompt = f"""Select the top 1-3 most relevant labels for the following GitHub issue or pull request.

INSTRUCTIONS:
1. Review the issue/PR title and description.
2. Consider the available labels and their descriptions.
3. Choose 1-3 labels that best match the issue/PR content.
4. Only use the "Alert" label when you have high confidence that this is an inappropriate issue.
5. Respond ONLY with the chosen label names (no descriptions), separated by commas.
6. If no labels are relevant, respond with 'None'.

AVAILABLE LABELS:
{labels}

ISSUE/PR TITLE:
{title}

ISSUE/PR DESCRIPTION:
{body[:16000]}

YOUR RESPONSE (label names only):
"""
    print(prompt)  # for short-term debugging
    messages = [
        {"role": "system", "content": "You are a helpful assistant that labels GitHub issues and pull requests."},
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


def apply_labels(number: int, labels: List[str]):
    """Applies the given labels to the issue or pull request."""
    if "Alert" in labels:
        create_alert_label()
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/issues/{number}/labels"
    response = requests.post(url, json={"labels": labels}, headers=GITHUB_HEADERS | {"Author": "UltralyticsAssistant"})
    if response.status_code == 200:
        print(f"Successfully applied labels: {', '.join(labels)}")
    else:
        print(f"Failed to apply labels. Status code: {response.status_code}")


def create_alert_label():
    """Creates the 'Alert' label in the repository if it doesn't exist."""
    alert_label = {
        "name": "Alert",
        "color": "FF0000",  # bright red
        "description": "Potential spam, abuse, or off-topic.",
    }
    response = requests.post(f"{GITHUB_API_URL}/repos/{REPO_NAME}/labels", json=alert_label, headers=GITHUB_HEADERS)
    if response.status_code == 201:
        print("Successfully created 'Alert' label.")
    elif response.status_code == 422:  # Label already exists
        print("'Alert' label already exists.")
    else:
        print(f"Failed to create 'Alert' label. Status code: {response.status_code}")


def is_org_member(username: str) -> bool:
    """Checks if a user is a member of the organization."""
    org_name = REPO_NAME.split("/")[0]
    url = f"{GITHUB_API_URL}/orgs/{org_name}/members/{username}"
    response = requests.get(url, headers=GITHUB_HEADERS)
    return response.status_code == 204  # 204 means the user is a member


def add_comment(number: int, comment: str):
    """Adds a comment to the issue or pull request."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/issues/{number}/comments"
    data = {"body": comment}
    response = requests.post(url, json=data, headers=GITHUB_HEADERS)
    if response.status_code == 201:
        print(f"Successfully added comment to {GITHUB_EVENT_NAME} #{number}.")
    else:
        print(f"Failed to add comment. Status code: {response.status_code}")


def get_first_interaction_response(issue_type: str, title: str, body: str, username: str, number: int) -> str:
    """Generates a custom response using LLM based on the issue/PR content and instructions."""
    example = FIRST_INTERACTION_ISSUE_INSTRUCTIONS if issue_type == "issue" else FIRST_INTERACTION_PR_INSTRUCTIONS

    org_name, repo_name = REPO_NAME.split("/")
    repo_url = f"https://github.com/{REPO_NAME}"
    diff = get_pr_diff(number)[:32000] if issue_type == "pull request" else ""

    prompt = f"""Generate a tailored response for a new GitHub {issue_type} based on the following context and content:

CONTEXT:
- Repository: {repo_name}
- Organization: {org_name}
- Repository URL: {repo_url}
- User: {username}

INSTRUCTIONS:
- Provide an optimal answer if a bug report or question
- Provide highly detailed best-practices guidelines for issue/PR submission
- INCLUDE ALL LINKS AND INSTRUCTIONS IN THE EXAMPLE BELOW, customized as appropriate
- Inform the user a human reviewer should respond soon with additional help
- Do not add a sign-off or valediction like "best regards" at the end of your response
- Only link to files or URLs in the example below, do not add external links
- Use emojis to enliven your response and code example and backlinks if they help

EXAMPLE:
{example}

{issue_type.upper()} TITLE:
{title}

{issue_type.upper()} DESCRIPTION:
{body[:16000]}

{"PULL REQUEST DIFF:" if issue_type == "pull request" else ""}
{diff if issue_type == "pull request" else ""}

YOUR RESPONSE:
"""
    print(f"\n\n{prompt}\n\n")  # for debug
    messages = [
        {
            "role": "system",
            "content": f"You are a helpful assistant responding to GitHub {issue_type}s for the {org_name} organization.",
        },
        {"role": "user", "content": prompt},
    ]
    return get_completion(messages)


def main():
    """Runs autolabel action and adds custom response for new issues/PRs."""
    number, title, body, username = get_event_content()
    available_labels = {label["name"]: label.get("description", "") for label in get_github_data("labels")}
    current_labels = [label["name"].lower() for label in get_github_data(f"issues/{number}/labels")]
    relevant_labels = get_relevant_labels(title, body, available_labels, current_labels)

    if relevant_labels:
        apply_labels(number, relevant_labels)
        if "Alert" in relevant_labels and not is_org_member(username):
            update_issue_pr_content(number)
            close_issue_pr(number)
            lock_issue_pr(number)
            if BLOCK_USER:
                block_user(username=get_github_data(f"issues/{number}")["user"]["login"])
    else:
        print("No relevant labels found or applied.")

    # Generate and add custom response for new issues/PRs
    with open(GITHUB_EVENT_PATH) as f:
        event_data = json.load(f)

    if event_data.get("action") == "opened":
        issue_type = "issue" if GITHUB_EVENT_NAME == "issues" else "pull request"
        custom_response = get_first_interaction_response(issue_type, title, body, username, number)
        add_comment(number, custom_response)


if __name__ == "__main__":
    main()
