# Ultralytics YOLO 🚀, AGPL-3.0 License https://ultralytics.com/license

import json
import os
import time
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-05-13")  # update as required
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_API_KEY = os.getenv("OPENAI_AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("OPENAI_AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("OPENAI_AZURE_API_VERSION", "2024-05-01-preview")  # update as required


def openai_client():
    """Returns OpenAI client instance."""
    from openai import AzureOpenAI, OpenAI

    return (
        AzureOpenAI(api_key=AZURE_API_KEY, api_version=AZURE_API_VERSION, azure_endpoint=AZURE_ENDPOINT)
        if AZURE_API_KEY and AZURE_ENDPOINT
        else OpenAI(api_key=OPENAI_API_KEY)
    )


def get_completion(messages: list, use_python_client: bool = False) -> str:
    """Get completion from OpenAI or Azure OpenAI."""
    if use_python_client:
        response = openai_client().chat.completions.create(model=OPENAI_MODEL, messages=messages)
        return response.choices[0].message.content.strip()

    # If not Python client then use REST API
    if AZURE_API_KEY and AZURE_ENDPOINT:
        url = f"{AZURE_ENDPOINT}/openai/deployments/{OPENAI_MODEL}/chat/completions?api-version={AZURE_API_VERSION}"
        headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
        data = {"messages": messages}
    else:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        data = {"model": OPENAI_MODEL, "messages": messages}

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def get_github_data(endpoint: str) -> dict:
    """Generic function to fetch data from GitHub API."""
    response = requests.get(f"{GITHUB_API_URL}/repos/{REPO_NAME}/{endpoint}", headers=GITHUB_HEADERS)
    response.raise_for_status()
    return response.json()


def get_event_content() -> Tuple[int, str, str, str]:
    """Extracts the number, title, body (excluding HTML comments), and username from the issue or pull request."""
    with open(GITHUB_EVENT_PATH, "r") as f:
        event_data = json.load(f)

    def remove_comments_from_body(body: str) -> str:
        """Removes HTML comment blocks from the body text."""
        return re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL).strip()

    if GITHUB_EVENT_NAME == "issues":
        item = event_data["issue"]
        body = remove_comments_from_body(item.get("body", ""))
        return item["number"], item["title"], body, item["user"]["login"]

    elif GITHUB_EVENT_NAME in ["pull_request", "pull_request_target"]:
        pr_number = event_data["pull_request"]["number"]

        # Check if this is a newly opened PR
        if event_data["action"] == "opened":
            print("New PR detected. Waiting 15s before fetching PR data...")
            time.sleep(15)

        # Fetch the latest PR data
        data = get_github_data(f"pulls/{pr_number}")
        return pr_number, data["title"], remove_comments_from_body(data.get("body", "")), data["user"]["login"]

    else:
        raise ValueError(f"Unsupported event type: {GITHUB_EVENT_NAME}")


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
{body[:8000]}

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


def main():
    """Runs autolabel action."""
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


if __name__ == "__main__":
    main()
