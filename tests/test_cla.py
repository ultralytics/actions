# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import base64
import json
from unittest.mock import MagicMock

import pytest

from actions import cla


def response(status=200, data=None):
    """Create a mock HTTP response."""
    result = MagicMock(status_code=status)
    result.json.return_value = data
    return result


def action(event_name="pull_request_target"):
    """Create a mock source-repository action."""
    result = MagicMock()
    result.repository = "ultralytics/example"
    result.event_name = event_name
    result.event_data = {
        "repository": {"id": 123, "full_name": result.repository},
        "pull_request": {"number": 7},
    }
    return result


def ledger_response(rows, sha="old-sha"):
    """Create a Contents API response for the established CLA schema."""
    content = base64.b64encode(json.dumps({"signedContributors": rows}).encode()).decode()
    return response(data={"content": content, "sha": sha})


def commits_response(authors, total=None, has_next=False, cursor=None):
    """Create a GraphQL response containing PR commit authors."""
    nodes = [{"commit": {"author": author}} for author in authors]
    commits = {
        "totalCount": len(nodes) if total is None else total,
        "nodes": nodes,
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
    }
    return response(data={"data": {"repository": {"pullRequest": {"commits": commits}}}})


def test_contributors_paginates_and_requires_verified_github_identity():
    """Collect linked authors while retaining unverified email identities as unknown."""
    source = action()
    authors = [
        {
            "email": "work@example.com",
            "user": {"databaseId": 1, "login": "person"},
        },
        {
            "email": "personal@example.com",
            "user": {"databaseId": 1, "login": "person"},
        },
        {"name": "Alias", "email": "2+alias@users.noreply.github.com", "user": None},
        {"name": "Unknown", "email": "private@example.com", "user": None},
        {"user": {"databaseId": 3, "login": "dependabot[bot]"}},
        {"user": {"databaseId": 4, "login": "other[bot]"}},
        {"user": {"databaseId": 5, "login": "bot-attacker"}},
    ]
    source.get.return_value = response(data={"user": {"id": 1, "login": "person"}})
    source.post.return_value = commits_response(authors)

    assert cla._contributors(source, 7) == [
        {"id": 1, "name": "person"},
        {"id": None, "name": "Alias"},
        {"id": None, "name": "Unknown"},
        {"id": 4, "name": "other[bot]"},
        {"id": 5, "name": "bot-attacker"},
    ]


def test_ledger_preserves_existing_schema_and_never_creates_missing_file():
    """Read the established ledger directly without a replacement creation path."""
    store = action()
    row = {"name": "old", "id": 1, "comment_id": 2, "created_at": "date", "repoId": 3, "pullRequestNo": 4}
    store.get.return_value = ledger_response([row])

    assert cla._ledger(store) == ({"signedContributors": [row]}, "old-sha")
    store.get.assert_called_once_with(
        "https://api.github.com/repos/ultralytics/cla/contents/signatures/version1/cla.json",
        params={"ref": "cla-signatures"},
    )


def test_contributors_fails_when_github_truncates_commits():
    """Fail instead of silently skipping commit authors beyond an API limit."""
    source = action()
    source.get.return_value = response(data={"user": {"id": 1, "login": "person"}})
    source.post.return_value = commits_response([{"name": "Unknown", "user": None}], total=2)

    with pytest.raises(RuntimeError, match="returned 1 of 2"):
        cla._contributors(source, 7)


def test_contributors_paginates_graphql_commits():
    """Follow GraphQL cursors beyond one hundred PR commits."""
    source = action()
    source.get.return_value = response(data={"user": {"id": 1, "login": "opener"}})
    first = [{"user": {"databaseId": i, "login": f"user-{i}"}} for i in range(2, 102)]
    source.post.side_effect = [
        commits_response(first, total=101, has_next=True, cursor="next"),
        commits_response([{"user": {"databaseId": 102, "login": "user-102"}}], total=101),
    ]

    assert len(cla._contributors(source, 7)) == 102
    assert source.post.call_args_list[1].kwargs["json"]["variables"]["cursor"] == "next"


def test_persist_rereads_and_merges_after_conflict():
    """Re-read and merge the signature ledger after a concurrent write conflict."""
    source, store = action(), action()
    old = {"id": 1}
    new = {"name": "new", "id": 2, "comment_id": 3, "created_at": "date", "repoId": 123, "pullRequestNo": 7}
    store.get.side_effect = [ledger_response([old], "sha-1"), ledger_response([old], "sha-2")]
    store.put.side_effect = [response(409), response(200)]

    cla._persist(store, [new], source, 7)

    assert store.put.call_count == 2
    written = json.loads(base64.b64decode(store.put.call_args.kwargs["json"]["content"]))
    assert written["signedContributors"] == [old, new]
    assert store.put.call_args.kwargs["json"]["sha"] == "sha-2"


def test_run_records_exact_sentence_and_updates_legacy_comment():
    """Persist an exact signature and reuse the legacy action's status comment."""
    source, store = action(), action()
    signing = {
        "id": 30,
        "body": cla.SIGN_COMMENT,
        "created_at": "date",
        "user": {"id": 2, "login": "new", "type": "User"},
    }
    bot = {"id": 40, "body": "Posted by the CLA Assistant Lite bot", "user": {"login": cla.BOT_LOGIN}}
    source.get.side_effect = [
        response(data={"user": {"id": 2, "login": "new"}}),
        response(data=[signing, bot]),
    ]
    source.post.return_value = commits_response([{"user": {"databaseId": 2, "login": "new"}}])
    store.get.side_effect = [ledger_response([]), ledger_response([])]
    store.put.return_value = response(200)

    cla.run(source, store)

    stored = json.loads(base64.b64decode(store.put.call_args.kwargs["json"]["content"]))["signedContributors"]
    assert stored == [
        {"name": "new", "id": 2, "comment_id": 30, "created_at": "date", "repoId": 123, "pullRequestNo": 7}
    ]
    assert cla.SIGN_COMMENT in cla._comment_body([], [{"id": 2, "name": "new"}], [])
    source.patch.assert_called_once()
    assert "All Contributors have signed" in source.patch.call_args.kwargs["json"]["body"]


@pytest.mark.parametrize("body", [f"{cla.SIGN_COMMENT}!", cla.SIGN_COMMENT.lower(), f" {cla.SIGN_COMMENT}"])
def test_run_rejects_similar_sentence_and_keeps_hard_failure(body):
    """Reject a modified signing sentence and leave the CLA gate failed."""
    source, store = action(), action()
    user = {"id": 2, "login": "new", "type": "User"}
    source.get.side_effect = [
        response(data={"user": {"id": 2, "login": "new"}}),
        response(data=[{"id": 30, "body": body, "created_at": "date", "user": user}]),
        response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"login": cla.BOT_LOGIN}}]),
    ]
    source.post.side_effect = [
        commits_response([{"user": {"databaseId": 2, "login": "new"}}]),
        response(201),
    ]
    store.get.return_value = ledger_response([])
    source.post.return_value = response(201)

    with pytest.raises(RuntimeError, match="must sign"):
        cla.run(source, store)

    store.put.assert_not_called()
    assert cla.SIGN_COMMENT in source.post.call_args.kwargs["json"]["body"]


def test_run_fails_unlinked_email_author():
    """Require commit authors with unlinked emails to link a GitHub account."""
    source, store = action(), action()
    source.get.side_effect = [
        response(data={"user": {"id": 2, "login": "new"}}),
        response(data=[]),
        response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"login": cla.BOT_LOGIN}}]),
    ]
    source.post.side_effect = [
        commits_response([{"name": "Unknown", "email": "private@example.com", "user": None}]),
        response(201),
    ]
    store.get.return_value = ledger_response([])
    source.post.return_value = response(201)

    with pytest.raises(RuntimeError, match="must sign"):
        cla.run(source, store)

    assert "not linked to a GitHub account" in source.post.call_args.kwargs["json"]["body"]


def test_run_requires_pr_opener_when_commit_identity_is_already_signed():
    """Require the submitter to sign even when forged commit metadata names a signer."""
    source, store = action(), action()
    source.get.side_effect = [
        response(data={"user": {"id": 9, "login": "submitter"}}),
        response(data=[]),
        response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"login": cla.BOT_LOGIN}}]),
    ]
    source.post.side_effect = [
        commits_response([{"user": {"databaseId": 1, "login": "signed-author"}}]),
        response(201),
    ]
    store.get.return_value = ledger_response([{"id": 1}])

    with pytest.raises(RuntimeError, match="must sign"):
        cla.run(source, store)

    assert "@submitter" in source.patch.call_args.kwargs["json"]["body"]


def test_create_comment_confirms_ambiguous_write_before_failing():
    """Treat an ambiguous comment response as success only when the marker exists."""
    source = action()
    source.post.return_value = response(502)
    source.get.return_value = response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"login": cla.BOT_LOGIN}}])

    cla._update_comment(source, 7, [], "body")

    source.get.assert_called_once()
    source.post.return_value.raise_for_status.assert_not_called()
    source.patch.assert_called_once()


def test_update_comment_ignores_marker_from_another_bot():
    """Adopt only comments owned by the authenticated GitHub Actions bot."""
    source = action()
    source.post.return_value = response(201)
    source.get.return_value = response(data=[{"id": 41, "body": cla.COMMENT_MARKER, "user": {"login": cla.BOT_LOGIN}}])
    other = [{"id": 40, "body": cla.COMMENT_MARKER, "user": {"login": "other[bot]"}}]

    cla._update_comment(source, 7, other, "body")

    source.post.assert_called_once()
    assert source.patch.call_args.args[0].endswith("/issues/comments/41")


def test_read_retries_transient_responses(monkeypatch):
    """Retry a transient GitHub read without changing unrelated API clients."""
    source = action()
    source.get.side_effect = [response(502), response(200, {"ok": True})]
    monkeypatch.setattr("actions.cla.time.sleep", MagicMock())

    assert cla._read(source, "get", "url").json() == {"ok": True}
    assert source.get.call_count == 2


def test_rerun_uses_exact_pr_head(monkeypatch):
    """Rerun the failed CLA workflow associated with the live PR head only."""
    source = action("issue_comment")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "ultralytics/example/.github/workflows/cla.yml@refs/heads/main")
    source.get.side_effect = [
        response(data={"head": {"ref": "feature", "sha": "exact"}}),
        response(
            data={
                "workflow_runs": [
                    {"id": 1, "head_sha": "stale", "conclusion": "failure"},
                    {"id": 2, "head_sha": "exact", "conclusion": "failure"},
                ]
            }
        ),
    ]

    cla._rerun_pr_check(source, 7)

    assert source.post.call_args.args[0].endswith("/actions/runs/2/rerun")


def test_rerun_leaves_queued_exact_head_to_complete(monkeypatch):
    """Let an incomplete exact-head check run after per-PR concurrency releases."""
    source = action("issue_comment")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "ultralytics/example/.github/workflows/cla.yml@refs/heads/main")
    source.get.side_effect = [
        response(data={"head": {"ref": "feature", "sha": "exact"}}),
        response(data={"workflow_runs": [{"id": 2, "head_sha": "exact", "conclusion": None}]}),
    ]

    cla._rerun_pr_check(source, 7)

    source.post.assert_not_called()
