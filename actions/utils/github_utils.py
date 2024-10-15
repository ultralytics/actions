# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import os

import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
GITHUB_HEADERS_DIFF = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}

PR_NUMBER = os.getenv("PR_NUMBER")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")


def get_pr_diff(pr_number: int) -> str:
    """Retrieves the diff content for a specified pull request in a GitHub repository."""
    url = f"{GITHUB_API_URL}/repos/{REPO_NAME}/pulls/{pr_number}"
    r = requests.get(url, headers=GITHUB_HEADERS_DIFF)
    return r.text if r.status_code == 200 else ""


def get_github_data(endpoint: str) -> dict:
    """Fetches GitHub repository data from a specified endpoint using the GitHub API."""
    r = requests.get(f"{GITHUB_API_URL}/repos/{REPO_NAME}/{endpoint}", headers=GITHUB_HEADERS)
    r.raise_for_status()
    return r.json()


def graphql_request(query: str, variables: dict = None) -> dict:
    """Executes a GraphQL query against the GitHub API and returns the response as a dictionary."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v4+json",
    }
    r = requests.post(f"{GITHUB_API_URL}/graphql", json={"query": query, "variables": variables}, headers=headers)
    r.raise_for_status()
    result = r.json()
    success = "data" in result and not result.get("errors")
    print(f"{'Successful' if success else 'Fail'} discussion GraphQL request: {result.get('errors', 'No errors')}")
    return result
