# Ultralytics YOLO 🚀, AGPL-3.0 License https://ultralytics.com/license

import json
import os
from typing import List, Tuple

import requests
from openai import AzureOpenAI, OpenAI

REPO_NAME = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_AZURE_API_KEY = os.getenv("OPENAI_AZURE_API_KEY")
OPENAI_AZURE_API_VERSION = os.getenv("OPENAI_AZURE_API_VERSION", "2024-05-01-preview")
OPENAI_AZURE_ENDPOINT = os.getenv("OPENAI_AZURE_ENDPOINT")
OPENAI_AZURE_BOTH = OPENAI_AZURE_API_KEY and OPENAI_AZURE_ENDPOINT
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-05-13")


def openai_client(azure=OPENAI_AZURE_BOTH):
    """Returns OpenAI client instance."""
    return (
        AzureOpenAI(
            api_key=OPENAI_AZURE_API_KEY, api_version=OPENAI_AZURE_API_VERSION, azure_endpoint=OPENAI_AZURE_ENDPOINT
        )
        if azure
        else OpenAI(api_key=OPENAI_API_KEY)
    )


def get_event_data():
    """Reads the event data from the GITHUB_EVENT_PATH file."""
    with open(GITHUB_EVENT_PATH, "r") as f:
        return json.load(f)


def get_repo_labels() -> List[str]:
    """Fetches all labels from the repository."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/labels"
    response = requests.get(url, headers=GITHUB_HEADERS)
    return [label["name"] for label in response.json()]


def get_issue_or_pr_content(event_data) -> Tuple[int, str, str]:
    """Extracts the number, title, and body from the issue or pull request."""
    if GITHUB_EVENT_NAME == "issues":
        return (event_data["issue"]["number"], event_data["issue"]["title"], event_data["issue"]["body"] or "")
    elif GITHUB_EVENT_NAME in ["pull_request", "pull_request_target"]:
        return (
            event_data["pull_request"]["number"],
            event_data["pull_request"]["title"],
            event_data["pull_request"]["body"] or "",
        )
    else:
        raise ValueError(f"Unsupported event type: {GITHUB_EVENT_NAME}")


def apply_labels(number: int, labels: List[str]):
    """Applies the given labels to the issue or pull request."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/issues/{number}/labels"
    data = {"labels": labels}
    response = requests.post(url, json=data, headers=GITHUB_HEADERS)
    if response.status_code == 200:
        print(f"Successfully applied labels: {', '.join(labels)}")
    else:
        print(f"Failed to apply labels. Status code: {response.status_code}")


def normalize_labels(suggested_labels: List[str], available_labels: List[str]) -> List[str]:
    """Filters labels to match available labels, adjusting capitalization and ignoring labels that don't match."""
    available_labels_lower = {label.lower(): label for label in available_labels}
    normalized_labels = []

    for label in suggested_labels:
        lower_label = label.lower()
        if lower_label in available_labels_lower:
            normalized_labels.append(available_labels_lower[lower_label])

    return normalized_labels


def get_relevant_labels(title: str, body: str, labels: List[str]) -> List[str]:
    """Uses OpenAI to determine the most relevant labels."""
    prompt = f"""
    Given the following issue or pull request:

    Title: {title}
    Body: {body}

    And the following available labels:
    {', '.join(labels)}

    Please select the top 1-3 most relevant labels for this issue or pull request. 
    Respond with only the label names, separated by commas. If no labels are relevant, respond with 'None'.
    """

    response = openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that labels GitHub issues and pull requests."},
            {"role": "user", "content": prompt},
        ],
    )

    suggested_labels = response.choices[0].message.content.strip()
    if suggested_labels.lower() == "none":
        return []

    suggested_label_list = [label.strip() for label in suggested_labels.split(",")]
    return normalize_labels(suggested_label_list, labels)


def main():
    event_data = get_event_data()
    number, title, body = get_issue_or_pr_content(event_data)

    repo_labels = get_repo_labels()
    relevant_labels = get_relevant_labels(title, body, repo_labels)

    if relevant_labels:
        apply_labels(number, relevant_labels)
    else:
        print("No relevant labels found or applied.")


if __name__ == "__main__":
    main()
