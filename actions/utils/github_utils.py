# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license
import json
import os
from pathlib import Path

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


def check_pypi_version(pyproject_toml="pyproject.toml"):
    """Compares local and PyPI package versions to determine if a new version should be published."""
    import tomllib  # requires Python>=3.11

    with open(pyproject_toml, "rb") as f:
        pyproject = tomllib.load(f)

    package_name = pyproject["project"]["name"]
    local_version = pyproject["project"].get("version", "dynamic")

    # If version is dynamic, extract it from the specified file
    if local_version == "dynamic":
        version_attr = pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"]
        module_path, attr_name = version_attr.rsplit(".", 1)
        with open(f"{module_path.replace('.', '/')}/__init__.py") as f:
            local_version = next(line.split("=")[1].strip().strip("'\"") for line in f if line.startswith(attr_name))

    print(f"Local Version: {local_version}")

    # Get online version from PyPI
    response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
    online_version = response.json()["info"]["version"] if response.status_code == 200 else None
    print(f"Online Version: {online_version or 'Not Found'}")

    # Determine if a new version should be published
    if online_version:
        local_ver = tuple(map(int, local_version.split(".")))
        online_ver = tuple(map(int, online_version.split(".")))
        major_diff = local_ver[0] - online_ver[0]
        minor_diff = local_ver[1] - online_ver[1]
        patch_diff = local_ver[2] - online_ver[2]

        publish = (
            (major_diff == 0 and minor_diff == 0 and 0 < patch_diff <= 2)
            or (major_diff == 0 and minor_diff == 1 and local_ver[2] == 0)
            or (major_diff == 1 and local_ver[1] == 0 and local_ver[2] == 0)
        )  # should publish an update
    else:
        publish = True  # publish as this is likely a first release

    return local_version, online_version, publish


def ultralytics_actions_info():
    """Print Ultralytics Actions information."""
    event_data = {}
    if GITHUB_EVENT_PATH:
        event_path = Path(GITHUB_EVENT_PATH)
        if event_path.exists():
            event_data = json.loads(event_path.read_text())

    pr = event_data.get("pull_request", {})
    pr_head_ref = pr.get("head", {}).get("ref")

    info = {
        "github.event_name": GITHUB_EVENT_NAME,
        "github.event.action": event_data.get("action"),
        "github.repository": REPO_NAME,
        "github.event.pull_request.number": pr.get("number"),
        "github.event.pull_request.head.repo.full_name": pr.get("head", {}).get("repo", {}).get("full_name"),
        "github.actor": os.environ.get("GITHUB_ACTOR"),
        "github.event.pull_request.head.ref": pr_head_ref,
        "github.ref": os.environ.get("GITHUB_REF"),
        "github.head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github.base_ref": os.environ.get("GITHUB_BASE_REF"),
    }

    if GITHUB_EVENT_NAME == "discussion":
        info.update(
            {
                "github.event.discussion.node_id": event_data.get("discussion", {}).get("node_id"),
                "github.event.discussion.number": event_data.get("discussion", {}).get("number"),
            }
        )

    # Calculate the maximum length of the keys for alignment
    max_key_length = max(len(key) for key in info.keys())

    # Print a header
    print("\nUltralytics Actions Information")

    # Print the information in a formatted way
    for key, value in info.items():
        print(f"{key:<{max_key_length + 2}}: {value}")

    # Print a footer
    print("\n")
