# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from actions import __version__

GITHUB_API_URL = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# GraphQL Queries
GRAPHQL_REPO_LABELS = """
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

GRAPHQL_PR_CONTRIBUTORS = """
query($owner: String!, $repo: String!, $pr_number: Int!) {
    repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr_number) {
            closingIssuesReferences(first: 50) { nodes { number } }
            url
            title
            author { login, __typename }
            reviews(first: 50) { nodes { author { login, __typename } } }
            comments(first: 50) { nodes { author { login, __typename } } }
            commits(first: 100) { nodes { commit { author { user { login } }, committer { user { login } } } } }
        }
    }
}
"""

GRAPHQL_UPDATE_DISCUSSION = """
mutation($discussionId: ID!, $title: String!, $body: String!) {
    updateDiscussion(input: {discussionId: $discussionId, title: $title, body: $body}) {
        discussion {
            id
        }
    }
}
"""

GRAPHQL_CLOSE_DISCUSSION = """
mutation($discussionId: ID!) {
    closeDiscussion(input: {discussionId: $discussionId}) {
        discussion {
            id
        }
    }
}
"""

GRAPHQL_LOCK_DISCUSSION = """
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

GRAPHQL_ADD_DISCUSSION_COMMENT = """
mutation($discussionId: ID!, $body: String!) {
    addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
        comment {
            id
        }
    }
}
"""

GRAPHQL_ADD_LABELS_TO_DISCUSSION = """
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

GRAPHQL_PR_DETAILS = """
query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
            body
        }
        labels(first: 100) {
            nodes {
                name
                description
            }
        }
    }
}
"""  # Note: Limited to first 100 labels. Sufficient for most repos; add pagination if needed.

GRAPHQL_PR_REVIEWS_COMMENTS = """
query($owner: String!, $repo: String!, $number: Int!, $botLogin: String!) {
    repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
            reviews(first: 100, author: $botLogin) {
                nodes {
                    databaseId
                    state
                    body
                    author { login }
                }
            }
            comments(last: 100) {
                nodes {
                    id
                    author { login }
                }
            }
        }
    }
}
"""

GRAPHQL_LABEL_AND_COMMENT_ISSUE = """
mutation($issueId: ID!, $labelIds: [ID!]!, $body: String!) {
    addLabelsToLabelable(input: {labelableId: $issueId, labelIds: $labelIds}) {
        labelable { id }
    }
    addComment(input: {subjectId: $issueId, body: $body}) {
        commentEdge { node { id } }
    }
}
"""


class Action:
    """Handles GitHub Actions API interactions and event processing."""

    def __init__(
        self,
        token: str | None = None,
        event_name: str | None = None,
        event_data: dict | None = None,
        verbose: bool = True,
    ):
        """Initializes a GitHub Actions API handler with token and event data for processing events."""
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.event_name = event_name or os.getenv("GITHUB_EVENT_NAME")
        self.event_data = event_data or self._load_event_data(os.getenv("GITHUB_EVENT_PATH"))
        self.pr = self.event_data.get("pull_request", {})
        self.repository = self.event_data.get("repository", {}).get("full_name")
        self.headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        self.headers_diff = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3.diff"}
        self.verbose = verbose
        self.eyes_reaction_id = None
        self._pr_diff_cache = None
        self._pr_summary_cache = None
        self._username_cache = None
        self._default_status = {
            "get": [200, 204],
            "post": [200, 201, 204],
            "put": [200, 201, 204],
            "patch": [200],
            "delete": [200, 204],
        }

    def _request(self, method: str, url: str, headers=None, expected_status=None, hard=False, **kwargs):
        """Unified request handler with error checking."""
        r = getattr(requests, method)(url, headers=headers or self.headers, **kwargs)
        expected = expected_status or self._default_status[method]
        success = r.status_code in expected

        if self.verbose:
            elapsed = r.elapsed.total_seconds()
            print(f"{'✓' if success else '✗'} {method.upper()} {url} → {r.status_code} ({elapsed:.1f}s)", flush=True)
            if not success:
                try:
                    error_data = r.json()
                    print(f"  ❌ Error: {error_data.get('message', 'Unknown error')}")
                    if errors := error_data.get("errors"):
                        print(f"  Details: {errors}")
                except Exception:
                    print(f"  ❌ Error: {r.text[:1000]}")

        if not success and hard:
            r.raise_for_status()
        return r

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
        return json.loads(Path(event_path).read_text()) if event_path and Path(event_path).exists() else {}

    def is_repo_private(self) -> bool:
        """Checks if the repository is public using event data."""
        return self.event_data.get("repository", {}).get("private", False)

    def get_username(self) -> str | None:
        """Gets username associated with the GitHub token with caching."""
        if self._username_cache:
            return self._username_cache

        response = self.post(GITHUB_GRAPHQL_URL, json={"query": "query { viewer { login } }"})
        if response.status_code == 200:
            try:
                self._username_cache = response.json()["data"]["viewer"]["login"]
            except KeyError as e:
                print(f"Error parsing authenticated user response: {e}")
        return self._username_cache

    def is_org_member(self, username: str) -> bool:
        """Checks if a user is a member of the organization."""
        return self.get(f"{GITHUB_API_URL}/orgs/{self.repository.split('/')[0]}/members/{username}").status_code == 204

    def should_skip_pr_author(self) -> bool:
        """Checks if PR should be skipped based on author (self-authored or bot PRs)."""
        if not self.pr:
            return False
        if pr_author := self.pr.get("user", {}).get("login"):
            if pr_author == self.get_username():
                print(f"Skipping: PR author ({pr_author}) is the same as bot")
                return True
            # Check both user.type and [bot] suffix for robust bot detection
            if self.pr.get("user", {}).get("type") == "Bot" or pr_author.endswith("[bot]"):
                print(f"Skipping: PR author ({pr_author}) is a bot")
                return True
        return False

    def is_fork_pr(self) -> bool:
        """Checks if PR is from a fork (different repo than base)."""
        if not self.pr:
            return False
        head_repo = self.pr.get("head", {}).get("repo", {}).get("full_name")
        return bool(head_repo) and head_repo != self.repository

    def should_skip_openai(self) -> bool:
        """Check if OpenAI operations should be skipped."""
        from actions.utils.openai_utils import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            print("⚠️ Skipping LLM operations (OPENAI_API_KEY not found)")
            return True
        return False

    def get_pr_diff(self) -> str:
        """Retrieves the diff content for a specified pull request with caching."""
        if self._pr_diff_cache:
            return self._pr_diff_cache

        url = f"{GITHUB_API_URL}/repos/{self.repository}/pulls/{self.pr.get('number')}"
        response = self.get(url, headers=self.headers_diff)
        if response.status_code == 200:
            self._pr_diff_cache = response.text or "ERROR: EMPTY DIFF, NO CODE CHANGES IN THIS PR."
        elif response.status_code == 406:
            self._pr_diff_cache = "ERROR: PR diff exceeds GitHub's 20,000 line limit, unable to retrieve diff."
        else:
            self._pr_diff_cache = "ERROR: UNABLE TO RETRIEVE DIFF."
        return self._pr_diff_cache

    def get_repo_data(self, endpoint: str) -> dict:
        """Fetches repository data from a specified endpoint."""
        return self.get(f"{GITHUB_API_URL}/repos/{self.repository}/{endpoint}").json()

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

    def graphql_request(self, query: str, variables: dict | None = None) -> dict:
        """Executes a GraphQL query against the GitHub API."""
        result = self.post(GITHUB_GRAPHQL_URL, json={"query": query, "variables": variables}).json()
        if "data" not in result or result.get("errors"):
            print(result.get("errors"))
        return result

    def update_pr_description(self, number: int, new_summary: str, current_body: str | None = None):
        """Updates PR description with summary, uses cached body if provided to avoid redundant API calls."""
        import time

        url = f"{GITHUB_API_URL}/repos/{self.repository}/pulls/{number}"
        if current_body is None:
            for i in range(3):
                current_body = self.get(url).json().get("body") or ""
                if current_body:
                    break
                if i < 2:
                    print("No current PR description found, retrying...")
                    time.sleep(1)

        start = "## 🛠️ PR Summary"
        if start in current_body:
            print("Existing PR Summary found, replacing.")
            updated_description = current_body.split(start)[0].rstrip() + "\n\n" + new_summary
        else:
            print("PR Summary not found, appending.")
            updated_description = (
                (current_body.rstrip() + "\n\n" + new_summary) if current_body.strip() else new_summary
            )

        self.patch(url, json={"body": updated_description})
        self._pr_summary_cache = new_summary

    def get_label_ids(self, labels: list[str]) -> list[str]:
        """Retrieves GitHub label IDs for a list of label names using the GraphQL API."""
        owner, repo = self.repository.split("/")
        result = self.graphql_request(GRAPHQL_REPO_LABELS, variables={"owner": owner, "name": repo})
        if "data" in result and "repository" in result["data"]:
            all_labels = result["data"]["repository"]["labels"]["nodes"]
            label_map = {label["name"].lower(): label["id"] for label in all_labels}
            return [label_map.get(label.lower()) for label in labels if label.lower() in label_map]
        return []

    def apply_labels(self, number: int, node_id: str, labels: list[str], issue_type: str):
        """Applies specified labels to a GitHub issue, pull request, or discussion."""
        if "Alert" in labels:
            self.create_alert_label()

        if issue_type == "discussion":
            label_ids = self.get_label_ids(labels)
            if not label_ids:
                print("No valid labels to apply.")
                return
            self.graphql_request(GRAPHQL_ADD_LABELS_TO_DISCUSSION, {"labelableId": node_id, "labelIds": label_ids})
        else:
            url = f"{GITHUB_API_URL}/repos/{self.repository}/issues/{number}/labels"
            self.post(url, json={"labels": labels})

    def create_alert_label(self):
        """Creates the 'Alert' label in the repository if it doesn't exist."""
        alert_label = {"name": "Alert", "color": "FF0000", "description": "Potential spam, abuse, or off-topic."}
        self.post(f"{GITHUB_API_URL}/repos/{self.repository}/labels", json=alert_label)

    def remove_labels(self, number: int, labels: tuple[str, ...]):
        """Removes specified labels from an issue or PR."""
        for label in labels:
            self.delete(f"{GITHUB_API_URL}/repos/{self.repository}/issues/{number}/labels/{label}")

    def add_comment(self, number: int, node_id: str, comment: str, issue_type: str):
        """Adds a comment to an issue, pull request, or discussion."""
        if issue_type == "discussion":
            self.graphql_request(GRAPHQL_ADD_DISCUSSION_COMMENT, variables={"discussionId": node_id, "body": comment})
        else:
            self.post(f"{GITHUB_API_URL}/repos/{self.repository}/issues/{number}/comments", json={"body": comment})

    def update_content(
        self, number: int, node_id: str, issue_type: str, title: str | None = None, body: str | None = None
    ):
        """Updates the title and/or body of an issue, pull request, or discussion."""
        if issue_type == "discussion":
            variables = {"discussionId": node_id}
            if title:
                variables["title"] = title
            if body:
                variables["body"] = body
            self.graphql_request(GRAPHQL_UPDATE_DISCUSSION, variables=variables)
        else:
            url = f"{GITHUB_API_URL}/repos/{self.repository}/issues/{number}"
            data = {}
            if title:
                data["title"] = title
            if body:
                data["body"] = body
            self.patch(url, json=data)

    def close_item(self, number: int, node_id: str, issue_type: str):
        """Closes an issue, pull request, or discussion."""
        if issue_type == "discussion":
            self.graphql_request(GRAPHQL_CLOSE_DISCUSSION, variables={"discussionId": node_id})
        else:
            url = f"{GITHUB_API_URL}/repos/{self.repository}/issues/{number}"
            self.patch(url, json={"state": "closed"})

    def lock_item(self, number: int, node_id: str, issue_type: str):
        """Locks an issue, pull request, or discussion to prevent further interactions."""
        if issue_type == "discussion":
            self.graphql_request(GRAPHQL_LOCK_DISCUSSION, variables={"lockableId": node_id, "lockReason": "OFF_TOPIC"})
        else:
            url = f"{GITHUB_API_URL}/repos/{self.repository}/issues/{number}/lock"
            self.put(url, json={"lock_reason": "off-topic"})

    def block_user(self, username: str):
        """Blocks a user from the organization."""
        url = f"{GITHUB_API_URL}/orgs/{self.repository.split('/')[0]}/blocks/{username}"
        self.put(url)

    def handle_alert(self, number: int, node_id: str, issue_type: str, username: str, block: bool = False):
        """Handles content flagged as alert: updates content, locks, optionally closes and blocks user."""
        new_title = "Content Under Review"
        new_body = """This post has been flagged for review by [Ultralytics Actions](https://www.ultralytics.com/actions) due to possible spam, abuse, or off-topic content. For more information please see our:

- [Code of Conduct](https://docs.ultralytics.com/help/code-of-conduct/)
- [Security Policy](https://docs.ultralytics.com/help/security/)

For questions or bug reports related to this action please visit https://github.com/ultralytics/actions.

Thank you 🙏
"""
        self.update_content(number, node_id, issue_type, title=new_title, body=new_body)
        if issue_type != "pull request":
            self.close_item(number, node_id, issue_type)
        self.lock_item(number, node_id, issue_type)
        if block:
            self.block_user(username)

    def get_pr_details_and_labels(self, pr_number: int) -> dict:
        """Gets PR details and repository labels in a single GraphQL query."""
        owner, repo = self.repository.split("/")
        variables = {"owner": owner, "repo": repo, "number": pr_number}
        result = self.graphql_request(GRAPHQL_PR_DETAILS, variables=variables)
        return result.get("data", {}).get("repository", {})

    def get_pr_reviews_and_comments(self, pr_number: int) -> tuple[list, list]:
        """Gets PR reviews and comments by bot in a single GraphQL query."""
        owner, repo = self.repository.split("/")
        bot_login = self.get_username()
        if not bot_login:
            return [], []

        variables = {"owner": owner, "repo": repo, "number": pr_number, "botLogin": bot_login}
        result = self.graphql_request(GRAPHQL_PR_REVIEWS_COMMENTS, variables=variables)

        pr_data = result.get("data", {}).get("repository", {}).get("pullRequest", {})
        reviews = pr_data.get("reviews", {}).get("nodes", [])
        comments = pr_data.get("comments", {}).get("nodes", [])
        return reviews, comments

    def batch_delete_review_comments(self, comment_ids: list[str]) -> None:
        """Batch delete PR review comments using a single GraphQL mutation (max 50 to avoid query limits)."""
        if not comment_ids:
            return

        # Limit to first 50 comments to avoid hitting GraphQL complexity limits
        comment_ids = comment_ids[:50]

        mutations = []
        for i, comment_id in enumerate(comment_ids):
            mutations.append(
                f'delete{i}: deletePullRequestReviewComment(input: {{id: "{comment_id}"}}) {{ clientMutationId }}'
            )

        mutation = f"mutation {{ {' '.join(mutations)} }}"
        self.graphql_request(mutation)

    def get_multiple_issue_node_ids(self, issue_numbers: list[int]) -> dict[int, str]:
        """Gets multiple issue node IDs in a single GraphQL query."""
        if not issue_numbers:
            return {}

        owner, repo = self.repository.split("/")

        # Build parameterized query to avoid injection risks
        query_parts = []
        for i in range(len(issue_numbers)):
            query_parts.append(f"issue{i}: issue(number: $num{i}) {{ id }}")

        variables = {f"num{i}": num for i, num in enumerate(issue_numbers)}
        variables["owner"] = owner
        variables["repo"] = repo

        # Build variable definitions
        var_defs = ["$owner: String!", "$repo: String!"] + [f"$num{i}: Int!" for i in range(len(issue_numbers))]

        query = f"""query({", ".join(var_defs)}) {{
            repository(owner: $owner, name: $repo) {{
                {" ".join(query_parts)}
            }}
        }}"""

        result = self.graphql_request(query, variables)
        repo_data = result.get("data", {}).get("repository", {})
        return {
            num: repo_data.get(f"issue{i}", {}).get("id")
            for i, num in enumerate(issue_numbers)
            if repo_data.get(f"issue{i}")
        }

    def get_pr_contributors(self) -> tuple[str | None, dict]:
        """Gets PR contributors and closing issues, returns (pr_credit_string, pr_data)."""
        owner, repo = self.repository.split("/")
        variables = {"owner": owner, "repo": repo, "pr_number": self.pr["number"]}
        response = self.post(GITHUB_GRAPHQL_URL, json={"query": GRAPHQL_PR_CONTRIBUTORS, "variables": variables})
        if response.status_code != 200:
            return None, {}

        try:
            data = response.json()["data"]["repository"]["pullRequest"]
            comments = data["reviews"]["nodes"] + data["comments"]["nodes"]
            username = self.get_username()
            author = data["author"]["login"] if data["author"]["__typename"] != "Bot" else None

            contributors = {x["author"]["login"] for x in comments if x["author"]["__typename"] != "Bot"}

            for commit in data["commits"]["nodes"]:
                commit_data = commit["commit"]
                for user_type in ["author", "committer"]:
                    if user := commit_data[user_type].get("user"):
                        if login := user.get("login"):
                            contributors.add(login)

            contributors.discard(author)
            contributors.discard(username)

            pr_credit = ""
            if author and author != username:
                pr_credit += f"@{author}"
            if contributors:
                pr_credit += (" with contributions from " if pr_credit else "") + ", ".join(
                    f"@{c}" for c in contributors
                )

            return pr_credit, data
        except KeyError as e:
            print(f"Error parsing GraphQL response: {e}")
            return None, {}

    def print_info(self):
        """Print GitHub Actions information including event details and repository information."""
        info = {
            "github.event_name": self.event_name,
            "github.event.action": self.event_data.get("action"),
            "github.repository": self.repository,
            "github.repository.private": self.is_repo_private(),
            "github.event.pull_request.number": self.pr.get("number"),
            "github.event.pull_request.head.repo.full_name": self.pr.get("head", {}).get("repo", {}).get("full_name"),
            "github.actor": os.getenv("GITHUB_ACTOR"),
            "github.event.pull_request.head.ref": self.pr.get("head", {}).get("ref"),
            "github.ref": os.getenv("GITHUB_REF"),
            "github.head_ref": os.getenv("GITHUB_HEAD_REF"),
            "github.base_ref": os.getenv("GITHUB_BASE_REF"),
            "github.base_sha": self.pr.get("base", {}).get("sha"),
        }

        if self.event_name == "discussion":
            discussion = self.event_data.get("discussion", {})
            info |= {
                "github.event.discussion.node_id": discussion.get("node_id"),
                "github.event.discussion.number": discussion.get("number"),
            }

        width = max(len(k) for k in info) + 5
        header = f"Ultralytics Actions {__version__} Information " + "-" * 40
        print(f"{header}\n" + "\n".join(f"{k:<{width}}{v}" for k, v in info.items()) + f"\n{'-' * len(header)}")


def ultralytics_actions_info():
    """Return GitHub Actions environment information and configuration details for Ultralytics workflows."""
    Action().print_info()
