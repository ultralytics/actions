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


def test_contributors_paginates_and_requires_verified_github_identity():
    """Collect linked authors while retaining unverified email identities as unknown."""
    source = action()
    commits = [
        {
            "author": {"id": 1, "login": "person", "type": "User"},
            "commit": {"author": {"email": "work@example.com"}},
        },
        {
            "author": {"id": 1, "login": "person", "type": "User"},
            "commit": {"author": {"email": "personal@example.com"}},
        },
        {
            "author": None,
            "commit": {"author": {"name": "Alias", "email": "2+alias@users.noreply.github.com"}},
        },
        {"author": None, "commit": {"author": {"name": "Unknown", "email": "private@example.com"}}},
        {"author": {"id": 3, "login": "dependabot[bot]", "type": "Bot"}, "commit": {"author": {}}},
        {"author": {"id": 4, "login": "other[bot]", "type": "Bot"}, "commit": {"author": {}}},
    ]
    source.get.side_effect = [response(data=commits), response(data={"commits": len(commits)})]

    assert cla._contributors(source, 7) == [
        {"id": 1, "name": "person"},
        {"id": None, "name": "Alias"},
        {"id": None, "name": "Unknown"},
        {"id": 4, "name": "other[bot]"},
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
        hard=True,
    )


def test_contributors_fails_when_github_truncates_commits():
    """Fail instead of silently skipping commit authors beyond an API limit."""
    source = action()
    source.get.side_effect = [response(data=[{"author": None}]), response(data={"commits": 2})]

    with pytest.raises(RuntimeError, match="returned 1 of 2"):
        cla._contributors(source, 7)


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
    bot = {"id": 40, "body": "Posted by the CLA Assistant Lite bot", "user": {"type": "Bot"}}
    source.get.side_effect = [
        response(data=[{"author": signing["user"], "commit": {"author": {}}}]),
        response(data={"commits": 1}),
        response(data=[signing, bot]),
    ]
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


def test_run_rejects_similar_sentence_and_keeps_hard_failure():
    """Reject a modified signing sentence and leave the CLA gate failed."""
    source, store = action(), action()
    user = {"id": 2, "login": "new", "type": "User"}
    source.get.side_effect = [
        response(data=[{"author": user, "commit": {"author": {}}}]),
        response(data={"commits": 1}),
        response(data=[{"id": 30, "body": f"{cla.SIGN_COMMENT}!", "created_at": "date", "user": user}]),
        response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"type": "Bot"}}]),
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
        response(data=[{"author": None, "commit": {"author": {"name": "Unknown", "email": "private@example.com"}}}]),
        response(data={"commits": 1}),
        response(data=[]),
        response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"type": "Bot"}}]),
    ]
    store.get.return_value = ledger_response([])
    source.post.return_value = response(201)

    with pytest.raises(RuntimeError, match="must sign"):
        cla.run(source, store)

    assert "not linked to a GitHub account" in source.post.call_args.kwargs["json"]["body"]


def test_create_comment_confirms_ambiguous_write_before_failing():
    """Treat an ambiguous comment response as success only when the marker exists."""
    source = action()
    source.post.return_value = response(502)
    source.get.return_value = response(data=[{"id": 40, "body": cla.COMMENT_MARKER, "user": {"type": "Bot"}}])

    cla._update_comment(source, 7, [], "body")

    source.get.assert_called_once()
    source.post.return_value.raise_for_status.assert_not_called()
    source.patch.assert_called_once()


def test_update_comment_reconciles_duplicates():
    """Keep the oldest bot-owned CLA comment and delete duplicate status comments."""
    source = action()
    comments = [
        {"id": 40, "body": cla.COMMENT_MARKER, "user": {"type": "Bot"}},
        {"id": 41, "body": "CLA Assistant Lite bot", "user": {"type": "Bot"}},
    ]
    source.delete.return_value = response(204)

    cla._update_comment(source, 7, comments, "body")

    assert source.patch.call_args.args[0].endswith("/issues/comments/40")
    assert source.delete.call_args.args[0].endswith("/issues/comments/41")


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


def test_rerun_waits_for_in_progress_exact_head(monkeypatch):
    """Wait for an in-flight exact-head check, then rerun it if it failed."""
    source = action("issue_comment")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "ultralytics/example/.github/workflows/cla.yml@refs/heads/main")
    monkeypatch.setattr("actions.cla.time.sleep", MagicMock())
    source.get.side_effect = [
        response(data={"head": {"ref": "feature", "sha": "exact"}}),
        response(data={"workflow_runs": [{"id": 2, "head_sha": "exact", "conclusion": None}]}),
        response(data={"id": 2, "head_sha": "exact", "conclusion": "failure"}),
    ]

    cla._rerun_pr_check(source, 7)

    assert source.post.call_args.args[0].endswith("/actions/runs/2/rerun")
