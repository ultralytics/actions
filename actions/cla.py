# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import base64
import json
import os
import re
import time

from .utils import GITHUB_API_URL, Action

CLA_REPOSITORY = "ultralytics/cla"
CLA_PATH = "signatures/version1/cla.json"
CLA_BRANCH = "cla-signatures"
CLA_DOCUMENT = "https://docs.ultralytics.com/help/CLA"
SIGN_COMMENT = "I have read the CLA Document and I sign the CLA"
COMMENT_MARKER = "<!-- ultralytics-cla -->"
LEGACY_MARKER = "CLA Assistant Lite bot"
ALLOWLIST = ("dependabot[bot]", "github-actions", "pre-commit*", "bot*")


def _matches(pattern: str, login: str) -> bool:
    """Match a GitHub login against a case-insensitive wildcard pattern."""
    return re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), login, re.IGNORECASE) is not None


def _paginate(action: Action, url: str) -> list[dict]:
    """Fetch every page from a GitHub REST collection."""
    items = []
    for page in range(1, 101):
        response = action.get(url, params={"per_page": 100, "page": page}, hard=True)
        page_items = response.json()
        items.extend(page_items)
        if len(page_items) < 100:
            return items
    raise RuntimeError(f"GitHub collection exceeded 10,000 items: {url}")


def _contributors(action: Action, number: int) -> list[dict]:
    """Return unique human commit authors, retaining unlinked authors as unsigned."""
    contributors = {}
    url = f"{GITHUB_API_URL}/repos/{action.repository}/pulls/{number}/commits"
    commits = _paginate(action, url)
    pr = action.get(f"{GITHUB_API_URL}/repos/{action.repository}/pulls/{number}", hard=True).json()
    if len(commits) != pr["commits"]:
        raise RuntimeError(f"GitHub returned {len(commits)} of {pr['commits']} PR commits")
    for commit in commits:
        raw_author = commit.get("commit", {}).get("author") or {}
        user = commit.get("author")
        login = user.get("login", "") if user else ""
        allowed = any(_matches(pattern, login) for pattern in ALLOWLIST) or (
            login.endswith("[bot]") and any(_matches(pattern, login[:-5]) for pattern in ALLOWLIST)
        )
        if user and not allowed:
            contributors[user["id"]] = {"id": user["id"], "name": user["login"]}
        elif not user:
            author = raw_author.get("name")
            if author:
                contributors[f"unknown:{author}"] = {"id": None, "name": author}
    return list(contributors.values())


def _ledger(action: Action) -> tuple[dict, str]:
    """Read and validate the existing central signature ledger."""
    url = f"{GITHUB_API_URL}/repos/{CLA_REPOSITORY}/contents/{CLA_PATH}"
    response = action.get(url, params={"ref": CLA_BRANCH}, hard=True)
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
    for _ in range(4):
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
        if response.status_code not in (409, 422, 429, 500, 502, 503, 504):
            response.raise_for_status()
    raise RuntimeError("CLA signature ledger changed repeatedly during update")


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
        if comment.get("user", {}).get("type") == "Bot"
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
            if comment.get("user", {}).get("type") == "Bot"
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
    for duplicate in existing[1:]:
        response = action.delete(f"{GITHUB_API_URL}/repos/{action.repository}/issues/comments/{duplicate['id']}")
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()


def _rerun_pr_check(action: Action, number: int) -> None:
    """Rerun the PR-head CLA workflow after a successful issue-comment signature."""
    if action.event_name != "issue_comment":
        return
    pr = action.get(f"{GITHUB_API_URL}/repos/{action.repository}/pulls/{number}", hard=True).json()
    workflow_ref = os.environ["GITHUB_WORKFLOW_REF"]
    workflow = workflow_ref.split(f"{action.repository}/", 1)[1].rsplit("@", 1)[0]
    run = None
    url = f"{GITHUB_API_URL}/repos/{action.repository}/actions/workflows/{workflow}/runs"
    for page in range(1, 101):
        runs = action.get(
            url,
            params={"branch": pr["head"]["ref"], "event": "pull_request_target", "per_page": 100, "page": page},
            hard=True,
        ).json()["workflow_runs"]
        run = next((item for item in runs if item["head_sha"] == pr["head"]["sha"]), None)
        if run or len(runs) < 100:
            break
    if not run:
        raise RuntimeError("Could not find the PR-head CLA workflow run")
    for _ in range(12):
        if run["conclusion"] is not None:
            break
        time.sleep(5)
        run = action.get(f"{GITHUB_API_URL}/repos/{action.repository}/actions/runs/{run['id']}", hard=True).json()
    if run["conclusion"] is None:
        raise RuntimeError("PR-head CLA workflow did not complete before the rerun timeout")
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
        if (comment.get("body") or "").strip().casefold() == SIGN_COMMENT.casefold()
        and comment.get("user", {}).get("id") in contributor_ids - signed_ids
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
