# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import json
import os
from pathlib import Path

import requests

from actions import __version__

GITHUB_API_URL = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


class Action:
    """Handles GitHub Actions API interactions and event processing."""

    def __init__(
        self,
        token: str = None,
        event_name: str = None,
        event_data: dict = None,
        verbose: bool = True,
    ):
        """Initializes a GitHub Actions API handler with token and event data for processing events."""
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.event_name = event_name or os.getenv("GITHUB_EVENT_NAME")
        self.event_data = event_data or self._load_event_data(os.getenv("GITHUB_EVENT_PATH"))
        self._default_status = {
            "get": [200],
            "post": [200, 201],
            "put": [200, 201, 204],
            "patch": [200],
            "delete": [200, 204],
        }

        self.pr = self.event_data.get("pull_request", {})
        self.repository = self.event_data.get("repository", {}).get("full_name")
        self.headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        self.headers_diff = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3.diff"}
        self.eyes_reaction_id = None
        self.verbose = verbose

    def _request(self, method: str, url: str, headers=None, expected_status=None, hard=False, **kwargs):
        """Unified request handler with error checking."""
        headers = headers or self.headers
        expected_status = expected_status or self._default_status[method.lower()]

        response = getattr(requests, method)(url, headers=headers, **kwargs)
        status = response.status_code
        success = status in expected_status

        if self.verbose:
            print(f"{'✓' if success else '✗'} {method.upper()} {url} → {status}")
            if not success:
                try:
                    error_detail = response.json()
                    print(f"  ❌ Error: {error_detail.get('message', 'Unknown error')}")
                except Exception as e:
                    print(f"  ❌ Error: {response.text[:100]}... {e}")

        if not success and hard:
            response.raise_for_status()

        return response

    def get(self, url, **kwargs):
        """Performs GET request with error handling."""
        return self._request("get", url, **kwargs)

    def post(self, url, **kwargs):
        """Performs POST request with error handling."""
        return self._request("post", url, **kwargs)

    def put(self, url, **kwargs):
        """Performs PUT request with error handling."""
        return self._request("put", url, **kwargs)

    def patch(self, url, **kwargs):
        """Performs PATCH request with error handling."""
        return self._request("patch", url, **kwargs)

    def delete(self, url, **kwargs):
        """Performs DELETE request with error handling."""
        return self._request("delete", url, **kwargs)

    @staticmethod
    def _load_event_data(event_path: str) -> dict:
        """Load GitHub event data from path if it exists."""
        if event_path and Path(event_path).exists():
            return json.loads(Path(event_path).read_text())
        return {}

    def is_repo_private(self) -> bool:
        """Checks if the repository is public using event data or GitHub API if needed."""
        return self.event_data.get("repository", {}).get("private")

    def get_username(self) -> str | None:
        """Gets username associated with the GitHub token."""
        response = self.post(GITHUB_GRAPHQL_URL, json={"query": "query { viewer { login } }"})
        if response.status_code == 200:
            try:
                return response.json()["data"]["viewer"]["login"]
            except KeyError as e:
                print(f"Error parsing authenticated user response: {e}")
        return None

    def is_org_member(self, username: str) -> bool:
        """Checks if a user is a member of the organization using the GitHub API."""
        org_name = self.repository.split("/")[0]
        response = self.get(f"{GITHUB_API_URL}/orgs/{org_name}/members/{username}")
        return response.status_code == 204  # 204 means the user is a member

    def get_pr_diff(self) -> str:
        """Retrieves the diff content for a specified pull request."""
        url = f"{GITHUB_API_URL}/repos/{self.repository}/pulls/{self.pr.get('number')}"
        response = self.get(url, headers=self.headers_diff)
        if response.status_code == 200:
            return response.text
        elif response.status_code == 406:
            return "**ERROR: DIFF TOO LARGE - PR exceeds GitHub's 20,000 line limit, unable to retrieve diff."
        else:
            return "**ERROR: UNABLE TO RETRIEVE DIFF."

    def get_repo_data(self, endpoint: str) -> dict:
        """Fetches repository data from a specified endpoint."""
        response = self.get(f"{GITHUB_API_URL}/repos/{self.repository}/{endpoint}")
        return response.json()

    def toggle_eyes_reaction(self, add: bool = True) -> None:
        """Adds or removes eyes emoji reaction."""
        if self.event_name in ["pull_request", "pull_request_target"]:
            id = self.pr.get("number")
        elif self.event_name == "issue_comment":
            id = f"comments/{self.event_data.get('comment', {}).get('id')}"
        else:
            id = self.event_data.get("issue", {}).get("number")
        if not id:
            return
        url = f"{GITHUB_API_URL}/repos/{self.repository}/issues/{id}/reactions"

        if add:
            response = self.post(url, json={"content": "eyes"})
            if response.status_code == 201:
                self.eyes_reaction_id = response.json().get("id")
        elif self.eyes_reaction_id:
            self.delete(f"{url}/{self.eyes_reaction_id}")
            self.eyes_reaction_id = None

    def graphql_request(self, query: str, variables: dict = None) -> dict:
        """Executes a GraphQL query against the GitHub API."""
        r = self.post(GITHUB_GRAPHQL_URL, json={"query": query, "variables": variables})
        result = r.json()
        if "data" not in result or result.get("errors"):
            print(result.get("errors"))
        return result

    def print_info(self):
        """Print GitHub Actions information including event details and repository information."""
        info = {
            "github.event_name": self.event_name,
            "github.event.action": self.event_data.get("action"),
            "github.repository": self.repository,
            "github.repository.private": self.is_repo_private(),
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
            info |= {
                "github.event.discussion.node_id": discussion.get("node_id"),
                "github.event.discussion.number": discussion.get("number"),
            }

        max_key_length = max(len(key) for key in info)
        header = f"Ultralytics Actions {__version__} Information " + "-" * 40
        print(header)
        for key, value in info.items():
            print(f"{key:<{max_key_length + 5}}{value}")
        print("-" * len(header))


def ultralytics_actions_info():
    """Return GitHub Actions environment information and configuration details for Ultralytics workflows."""
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
