# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license
import json
import os
from pathlib import Path

import requests

from actions import __version__

GITHUB_API_URL = "https://api.github.com"


class Action:
    """Handles GitHub Actions API interactions and event processing."""

    def __init__(
        self,
        token: str = None,
        event_name: str = None,
        event_data: dict = None,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.event_name = event_name or os.getenv("GITHUB_EVENT_NAME")
        self.event_data = event_data or self._load_event_data(os.getenv("GITHUB_EVENT_PATH"))

        self.pr = self.event_data.get("pull_request", {})
        self.repository = self.event_data.get("repository", {}).get("full_name")
        self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        self.headers_diff = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3.diff"}

    @staticmethod
    def _load_event_data(event_path: str) -> dict:
        """Loads GitHub event data from path if it exists."""
        if event_path and Path(event_path).exists():
            return json.loads(Path(event_path).read_text())
        return {}

    def get_username(self) -> str | None:
        """Gets username associated with the GitHub token."""
        query = "query { viewer { login } }"
        response = requests.post(f"{GITHUB_API_URL}/graphql", json={"query": query}, headers=self.headers)
        if response.status_code != 200:
            print(f"Failed to fetch authenticated user. Status code: {response.status_code}")
            return None
        try:
            return response.json()["data"]["viewer"]["login"]
        except KeyError as e:
            print(f"Error parsing authenticated user response: {e}")
            return None

    def get_pr_diff(self) -> str:
        """Retrieves the diff content for a specified pull request."""
        url = f"{GITHUB_API_URL}/repos/{self.repository}/pulls/{self.pr.get('number')}"
        r = requests.get(url, headers=self.headers_diff)
        return r.text if r.status_code == 200 else ""

    def get_repo_data(self, endpoint: str) -> dict:
        """Fetches repository data from a specified endpoint."""
        r = requests.get(f"{GITHUB_API_URL}/repos/{self.repository}/{endpoint}", headers=self.headers)
        r.raise_for_status()
        return r.json()

    def graphql_request(self, query: str, variables: dict = None) -> dict:
        """Executes a GraphQL query against the GitHub API."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v4+json",
        }
        r = requests.post(f"{GITHUB_API_URL}/graphql", json={"query": query, "variables": variables}, headers=headers)
        r.raise_for_status()
        result = r.json()
        success = "data" in result and not result.get("errors")
        print(
            f"{'Successful' if success else 'Failed'} discussion GraphQL request: {result.get('errors', 'No errors')}"
        )
        return result

    def print_info(self):
        """Print GitHub Actions information."""
        info = {
            "github.event_name": self.event_name,
            "github.event.action": self.event_data.get("action"),
            "github.repository": self.repository,
            "github.event.pull_request.number": self.pr.get("number"),
            "github.event.pull_request.head.repo.full_name": self.pr.get("head", {}).get("repo", {}).get("full_name"),
            "github.actor": os.environ.get("GITHUB_ACTOR"),
            "github.event.pull_request.head.ref": self.pr.get("head", {}).get("ref"),
            "github.ref": os.environ.get("GITHUB_REF"),
            "github.head_ref": os.environ.get("GITHUB_HEAD_REF"),
            "github.base_ref": os.environ.get("GITHUB_BASE_REF"),
            "github.base_sha": self.pr.get("base", {}).get("sha"),
        }

        if self.event_name == "discussion":
            discussion = self.event_data.get("discussion", {})
            info.update(
                {
                    "github.event.discussion.node_id": discussion.get("node_id"),
                    "github.event.discussion.number": discussion.get("number"),
                }
            )

        max_key_length = max(len(key) for key in info)
        header = f"Ultralytics Actions {__version__} Information " + "-" * 40
        print(header)
        for key, value in info.items():
            print(f"{key:<{max_key_length + 5}}{value}")
        print("-" * len(header))


def ultralytics_actions_info():
    Action().print_info()


def check_pypi_version(pyproject_toml="pyproject.toml"):
    """Compares local and PyPI package versions to determine if a new version should be published."""
    import re

    import tomllib  # requires Python>=3.11

    version_pattern = re.compile(r"^\d+\.\d+\.\d+$")  # e.g. 0.0.0

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
    if not bool(version_pattern.match(local_version)):
        print("WARNING: Incorrect local version pattern")
        return "0.0.0", "0.0.0", False

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
