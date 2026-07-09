# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "requests==2.32.4; python_version < '3.10'",
#   "requests==2.33.0; python_version >= '3.10'",
# ]
# ///

from __future__ import annotations

import base64
import json
import os
import time

from actions.utils import GITHUB_API_URL, GITHUB_GRAPHQL_URL, Action

CLA_REPOSITORY = "ultralytics/cla"
CLA_PATH = "signatures/version1/cla.json"
CLA_BRANCH = "cla-signatures"
CLA_DOCUMENT = "https://docs.ultralytics.com/help/CLA"
SIGN_COMMENT = "I have read the CLA Document and I sign the CLA"
COMMENT_MARKER = "<!-- ultralytics-cla -->"
LEGACY_MARKER = "CLA Assistant Lite bot"
BOT_LOGIN = "github-actions[bot]"
ALLOWLIST = frozenset(("dependabot[bot]", "github-actions[bot]", "pre-commit-ci[bot]"))
TRANSIENT_STATUS = (429, 500, 502, 503, 504)
COMMITS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      commits(first: 100, after: $cursor) {
        totalCount
        nodes {
          commit {
            author {
              name
              email
              user { databaseId login }
            }
          }
        }
        pageInfo { endCursor hasNextPage }
      }
    }
  }
}
"""


def _allowed(login: str) -> bool:
    """Return whether a GitHub login matches the configured bot allowlist."""
    return login.casefold() in ALLOWLIST


def _read(action: Action, method: str, url: str, **kwargs):
    """Retry a read-only GitHub request on transient responses."""
    for attempt in range(4):
        response = getattr(action, method)(url, **kwargs)
        if response.status_code not in TRANSIENT_STATUS:
            response.raise_for_status()
            return response
        if attempt < 3:
            time.sleep(float(response.headers.get("Retry-After", 2**attempt)))
    response.raise_for_status()


def _paginate(action: Action, url: str) -> list[dict]:
    """Fetch every page from a GitHub REST collection."""
    items = []
    for page in range(1, 101):
        response = _read(action, "get", url, params={"per_page": 100, "page": page})
        page_items = response.json()
        items.extend(page_items)
        if len(page_items) < 100:
            return items
    raise RuntimeError(f"GitHub collection exceeded 10,000 items: {url}")


def _contributors(action: Action, number: int) -> list[dict]:
    """Return the PR opener and every unique commit author."""
    contributors = {}
    pr = _read(action, "get", f"{GITHUB_API_URL}/repos/{action.repository}/pulls/{number}").json()
    opener = pr["user"]
    if not _allowed(opener["login"]):
        contributors[opener["id"]] = {"id": opener["id"], "name": opener["login"]}

    owner, name = action.repository.split("/", 1)
    cursor = None
    count = 0
    for _ in range(100):
        response = _read(
            action,
            "post",
            GITHUB_GRAPHQL_URL,
            json={
                "query": COMMITS_QUERY,
                "variables": {"owner": owner, "name": name, "number": number, "cursor": cursor},
            },
        ).json()
        if response.get("errors"):
            raise RuntimeError(f"Could not read PR commit authors: {response['errors']}")
        commits = response["data"]["repository"]["pullRequest"]["commits"]
        for node in commits["nodes"]:
            author = node["commit"].get("author") or {}
            user = author.get("user")
            if user and not _allowed(user["login"]):
                contributors[user["databaseId"]] = {"id": user["databaseId"], "name": user["login"]}
            elif not user and author.get("name"):
                key = f"unknown:{author['name']}:{author.get('email', '')}"
                contributors[key] = {"id": None, "name": author["name"]}
        count += len(commits["nodes"])
        if not commits["pageInfo"]["hasNextPage"]:
            if count != commits["totalCount"]:
                raise RuntimeError(f"GitHub returned {count} of {commits['totalCount']} PR commits")
            return list(contributors.values())
        cursor = commits["pageInfo"]["endCursor"]
    raise RuntimeError("Pull request exceeded 10,000 commits")


def _ledger(action: Action) -> tuple[dict, str]:
    """Read and validate the existing central signature ledger."""
    url = f"{GITHUB_API_URL}/repos/{CLA_REPOSITORY}/contents/{CLA_PATH}"
    response = _read(action, "get", url, params={"ref": CLA_BRANCH})
    payload = response.json()
    content = json.loads(base64.b64decode(payload["content"]))
    if not isinstance(content.get("signedContributors"), list):
        raise RuntimeError("CLA signature ledger has an invalid schema")
    return content, payload["sha"]


def _comments(action: Action, number: int) -> list[dict]:
    """Return every PR comment."""
    return _paginate(action, f"{GITHUB_API_URL}/repos/{action.repository}/issues/{number}/comments")


def _record(comment: dict, action: Action, number: int) -> dict:
    """Convert a signing comment to the established ledger schema."""
    user = comment["user"]
    return {
        "name": user["login"],
        "id": user["id"],
        "comment_id": comment["id"],
        "created_at": comment["created_at"],
        "repoId": action.event_data["repository"]["id"],
        "pullRequestNo": number,
    }


def _persist(action: Action, records: list[dict], source: Action, number: int) -> None:
    """Merge new signatures into the ledger with optimistic concurrency."""
    url = f"{GITHUB_API_URL}/repos/{CLA_REPOSITORY}/contents/{CLA_PATH}"
    for attempt in range(4):
        content, sha = _ledger(action)
        signed_ids = {row["id"] for row in content["signedContributors"]}
        additions = [row for row in records if row["id"] not in signed_ids]
        if not additions:
            return
        content["signedContributors"].extend(additions)
        names = ", ".join(f"@{row['name']}" for row in additions)
        response = action.put(
            url,
            json={
                "message": f"{names} signed the CLA in {source.repository}#{number}",
                "content": base64.b64encode(json.dumps(content, indent=2).encode()).decode(),
                "sha": sha,
                "branch": CLA_BRANCH,
            },
        )
        if response.status_code in (200, 201):
            return
        if response.status_code not in (409, 429, 500, 502, 503, 504):
            response.raise_for_status()
        if response.status_code != 409 and attempt < 3:
            time.sleep(float(response.headers.get("Retry-After", 2**attempt)))
    response.raise_for_status()


def _comment_body(signed: list[dict], unsigned: list[dict], unknown: list[dict]) -> str:
    """Build the single CLA status comment."""
    if not unsigned and not unknown:
        return f"{COMMENT_MARKER}\nAll Contributors have signed the CLA. ✅"
    names = "\n".join(f"- {'✅' if user in signed else '❌'} @{user['name']}" for user in signed + unsigned)
    if unknown:
        names += "\n" + "\n".join(f"- ❌ {user['name']} (not linked to a GitHub account)" for user in unknown)
    return f"""{COMMENT_MARKER}
Thank you for your contribution. Before it can be accepted, every contributor must sign our [Contributor License Agreement]({CLA_DOCUMENT}) by posting this exact comment:

> {SIGN_COMMENT}

{names}
"""


def _update_comment(action: Action, number: int, comments: list[dict], body: str) -> None:
    """Create or update one bot-owned CLA status comment."""
    existing = [
        comment
        for comment in comments
        if comment.get("user", {}).get("login") == BOT_LOGIN
        and (COMMENT_MARKER in (comment.get("body") or "") or LEGACY_MARKER in (comment.get("body") or ""))
    ]
    if not existing:
        response = action.post(
            f"{GITHUB_API_URL}/repos/{action.repository}/issues/{number}/comments",
            json={"body": body},
        )
        existing = [
            comment
            for comment in _comments(action, number)
            if comment.get("user", {}).get("login") == BOT_LOGIN
            and (COMMENT_MARKER in (comment.get("body") or "") or LEGACY_MARKER in (comment.get("body") or ""))
        ]
        if not existing:
            response.raise_for_status()
            raise RuntimeError("GitHub did not return the created CLA status comment")

    action.patch(
        f"{GITHUB_API_URL}/repos/{action.repository}/issues/comments/{existing[0]['id']}",
        json={"body": body},
        hard=True,
    )


def _rerun_pr_check(action: Action, number: int) -> None:
    """Rerun the PR-head CLA workflow after a successful issue-comment signature."""
    if action.event_name != "issue_comment":
        return
    pr = _read(action, "get", f"{GITHUB_API_URL}/repos/{action.repository}/pulls/{number}").json()
    workflow_ref = os.environ["GITHUB_WORKFLOW_REF"]
    workflow = workflow_ref.split(f"{action.repository}/", 1)[1].rsplit("@", 1)[0]
    run = None
    url = f"{GITHUB_API_URL}/repos/{action.repository}/actions/workflows/{workflow}/runs"
    for page in range(1, 101):
        runs = _read(
            action,
            "get",
            url,
            params={"branch": pr["head"]["ref"], "event": "pull_request_target", "per_page": 100, "page": page},
        ).json()["workflow_runs"]
        run = next((item for item in runs if item["head_sha"] == pr["head"]["sha"]), None)
        if run or len(runs) < 100:
            break
    if not run:
        raise RuntimeError("Could not find the PR-head CLA workflow run")
    if run["conclusion"] is None:
        return
    if run["conclusion"] != "success":
        action.post(f"{GITHUB_API_URL}/repos/{action.repository}/actions/runs/{run['id']}/rerun", hard=True)


def run(action: Action, ledger_action: Action) -> None:
    """Check the PR contributors against the central CLA ledger."""
    number = (action.event_data.get("pull_request") or action.event_data.get("issue"))["number"]
    contributors = _contributors(action, number)
    comments = _comments(action, number)
    content, _ = _ledger(ledger_action)
    signed_ids = {row["id"] for row in content["signedContributors"]}
    contributor_ids = {user["id"] for user in contributors if user["id"] is not None}
    records = {
        comment["user"]["id"]: _record(comment, action, number)
        for comment in comments
        if comment.get("body") == SIGN_COMMENT and comment.get("user", {}).get("id") in contributor_ids - signed_ids
    }
    if records:
        _persist(ledger_action, list(records.values()), action, number)
        signed_ids.update(records)

    signed = [user for user in contributors if user["id"] in signed_ids]
    unsigned = [user for user in contributors if user["id"] is not None and user["id"] not in signed_ids]
    unknown = [user for user in contributors if user["id"] is None]
    _update_comment(action, number, comments, _comment_body(signed, unsigned, unknown))
    if unsigned or unknown:
        raise RuntimeError("All PR contributors must sign the CLA")
    _rerun_pr_check(action, number)


def main() -> None:
    """Run the CLA check from GitHub Actions environment variables."""
    token = os.environ["GITHUB_TOKEN"]
    cla_token = os.environ["CLA_TOKEN"]
    action = Action(token=token)
    run(action, Action(token=cla_token, event_name=action.event_name, event_data=action.event_data))


if __name__ == "__main__":
    main()
