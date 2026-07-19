# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, call, patch

import pytest

from actions import first_interaction, review_pr
from actions.first_interaction import get_event_content, get_first_interaction_response, get_relevant_labels


def test_get_event_content_issue():
    """Test extracting content from issue event."""
    # Create mock event
    mock_event = MagicMock()
    mock_event.event_name = "issues"
    mock_event.event_data = {
        "action": "opened",
        "issue": {
            "number": 123,
            "node_id": "node123",
            "title": "Test Issue",
            "body": "Issue description",
            "user": {"login": "testuser"},
        },
    }

    number, node_id, title, body, username, issue_type, action = get_event_content(mock_event)

    assert number == 123
    assert node_id == "node123"
    assert title == "Test Issue"
    assert body == "Issue description"
    assert username == "testuser"
    assert issue_type == "issue"
    assert action == "opened"


def test_get_event_content_pr():
    """Test extracting content from PR event."""
    # Create mock event
    mock_event = MagicMock()
    mock_event.event_name = "pull_request"
    mock_event.event_data = {"action": "opened", "pull_request": {"number": 456}}

    # Mock PR data returned from API
    mock_event.get_repo_data.return_value = {
        "number": 456,
        "node_id": "node456",
        "title": "Test PR",
        "body": "PR description",
        "user": {"login": "testuser"},
    }

    number, node_id, title, body, username, issue_type, action = get_event_content(mock_event)

    assert number == 456
    assert node_id == "node456"
    assert title == "Test PR"
    assert body == "PR description"
    assert username == "testuser"
    assert issue_type == "pull request"
    assert action == "opened"


@patch("actions.first_interaction.review_pr.post_review_summary")
@patch("actions.first_interaction.review_pr.generate_pr_review")
@patch("actions.first_interaction.get_pr_open_response")
@patch("actions.first_interaction.get_event_content")
@patch("actions.first_interaction.Action")
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "PR description\n\nDeleted: superseded registry entries.",
            "PR description\n\nDeleted: superseded registry entries.",
        ),
        ("Short description.", "Short description.\n\nGenerated summary"),
        ("", "Generated summary"),
    ],
)
def test_open_pr_review_description(mock_action, mock_content, mock_response, mock_review, mock_post, body, expected):
    """Test automatic reviews use the best available author and generated description context."""
    mock_content.return_value = (456, "node456", "Test PR", body, "testuser", "pull request", "opened")
    mock_response.return_value = {"summary": "Generated summary", "labels": [], "first_comment": ""}
    mock_review.return_value = {"head_sha": "headsha", "summary": "LGTM", "comments": []}
    event = mock_action.return_value
    event.should_skip_llm.return_value = False
    event.should_skip_pr_author.return_value = False
    event.get_repo_data.return_value = []
    event.get_pr_diff.return_value = "diff"
    event.get_pr_diff_snapshot.return_value = ("review diff", "headsha")

    first_interaction.main()

    mock_review.assert_called_once_with(event.repository, "review diff", "Test PR", expected, event, "headsha")
    mock_post.assert_called_once_with(event, mock_review.return_value)


@patch("actions.first_interaction.get_response")
def test_get_relevant_labels(mock_get_response):
    """Test getting relevant labels for an issue."""
    mock_get_response.return_value = "bug, enhancement"

    available_labels = {
        "bug": "A bug in the software",
        "enhancement": "New feature or request",
        "documentation": "Improvements to documentation",
    }

    labels = get_relevant_labels(
        issue_type="issue",
        title="Bug: App crashes on startup",
        body="The application crashes when started",
        available_labels=available_labels,
        current_labels=[],
    )

    assert labels == ["bug", "enhancement"]
    mock_get_response.assert_called_once()


@patch("actions.first_interaction.get_response")
def test_get_first_interaction_response(mock_get_response):
    """Test generating first interaction response."""
    mock_get_response.return_value = "Thank you for your issue"

    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    response = get_first_interaction_response(
        event=mock_event, issue_type="issue", title="Test Issue", body="Issue description", username="testuser"
    )

    assert response == "Thank you for your issue"
    mock_get_response.assert_called_once()


@patch("actions.review_pr._verified_local_checkout", return_value=True)
@patch("actions.review_pr.get_agent_response")
def test_generate_pr_review_uses_synchronous_response(mock_get_agent_response, mock_checkout, tmp_path, monkeypatch):
    """Test PR reviews avoid background polling for code diffs."""
    monkeypatch.chdir(tmp_path)
    mock_get_agent_response.return_value = {"comments": [], "summary": "LGTM"}
    mock_event = MagicMock()
    mock_event.repository = "ultralytics/actions"
    mock_event.pr = {"number": 1, "head": {"sha": "headsha"}}
    api_response = MagicMock(status_code=200, text="")
    api_response.json.return_value = {"head": {"sha": "headsha"}}
    mock_event.get.return_value = api_response
    diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old = True
+old = False
"""

    review = review_pr.generate_pr_review("ultralytics/actions", diff, "Test PR", "", event=mock_event)

    assert review["summary"] == "LGTM"
    mock_get_agent_response.assert_called_once()
    kwargs = mock_get_agent_response.call_args.kwargs
    assert "background" not in kwargs
    assert kwargs["tools"][0]["type"] == "web_search"
    assert "filters" not in kwargs["tools"][0]
    assert {tool.get("name") for tool in kwargs["tools"] if tool.get("type") == "function"} == {
        "list_changed_files",
        "list_files",
        "read_diff",
        "read_file",
        "search_repo",
    }
    assert kwargs["max_turns"] == review_pr.MAX_AGENT_TURNS
    assert kwargs["max_cost"] == review_pr.REVIEW_COST_SOFT_LIMIT
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["request_timeout"] == (30, 120)
    assert "FULL FILE CONTENTS" not in mock_get_agent_response.call_args.args[0][1]["content"]


def test_review_agent_search_scans_local_checkout_only(tmp_path, monkeypatch):
    """Test repo search scans the local checkout without escaping it and is dropped without a checkout."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "secret.py").write_text("secret = True\n", encoding="utf-8")
    (tmp_path / "patterns.py").write_text("literal = '(a+)+$'\n", encoding="utf-8")
    workflow = tmp_path / ".github" / "workflows" / "format.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("workflow = True\n", encoding="utf-8")
    outside = tmp_path.parent / "outside_secret.py"
    outside.write_text("outside_secret = True\n", encoding="utf-8")
    (tmp_path / "linked_secret.py").symlink_to(outside)

    tools, handlers = review_pr.build_review_agent_tools(local_checkout=True)

    assert "search_repo" in {t.get("name") for t in tools}
    assert "1: secret = True" in handlers["read_file"](path="secret.py", start_line=None, end_line=None)
    assert "path must stay inside repository" in handlers["read_file"](
        path="linked_secret.py", start_line=None, end_line=None
    )
    assert "secret.py" in handlers["list_files"](path_glob=None).splitlines()
    assert ".github/workflows/format.yml" in handlers["list_files"](path_glob=".github/**").splitlines()
    assert "secret.py:1:secret = True" in handlers["search_repo"](query="secret = True", path_glob=None)
    assert "No matches found." == handlers["search_repo"](query="secret.*True", path_glob=None)
    assert "patterns.py:1:literal = '(a+)+$'" in handlers["search_repo"](query="(a+)+$", path_glob=None)
    assert ".github/workflows/format.yml:1:workflow = True" in handlers["search_repo"](
        query="workflow = True", path_glob=".github/**"
    )
    assert "No matches found." == handlers["search_repo"](query="outside_secret = True", path_glob=None)

    tools, handlers = review_pr.build_review_agent_tools(local_checkout=False)
    assert "search_repo" not in handlers
    assert "search_repo" not in {t.get("name") for t in tools}


def test_pr_head_sha_prefers_live_value():
    """Test head SHA resolution requires the live PR value."""
    event = MagicMock()
    event.repository = "org/repo"
    event.pr = {"number": 5, "head": {"sha": "old"}}
    live = MagicMock(status_code=200)
    live.json.return_value = {"head": {"sha": "new"}}
    event.get.return_value = live
    assert review_pr.Action.get_pr_head_sha(event) == "new"
    event.get.return_value = MagicMock(status_code=500)
    assert review_pr.Action.get_pr_head_sha(event) is None


def test_review_snapshot_retries_until_diff_and_head_match():
    """Test review snapshots refetch the diff when a push races the first request."""
    event = MagicMock()
    event.get_pr_head_sha.side_effect = ["old", "new", "new", "new"]
    event.get_pr_diff.side_effect = ["old diff", "new diff"]

    assert review_pr.Action.get_pr_diff_snapshot(event) == ("new diff", "new")
    assert event.get_pr_diff.call_args_list == [call(refresh=True), call(refresh=True)]
    assert event.get_pr_head_sha.call_count == 4


def test_post_review_summary_fails_when_github_rejects_review():
    """Test review publication is a required operation rather than a silent best effort."""
    event = MagicMock()
    event.repository = "org/repo"
    event.pr = {"number": 7}
    event.get_pr_head_sha.return_value = "abc"

    review_pr.post_review_summary(event, {"head_sha": "abc", "summary": "LGTM", "comments": []})

    assert event.post.call_args.kwargs["hard"] is True


def test_clear_previous_review_preserves_summaries_and_deletes_inline_comments():
    """Test replacement reviews invalidate bot decisions and remove only bot inline comments."""
    event = MagicMock()
    event.repository = "org/repo"
    event.pr = {"number": 7}
    event.get_username.return_value = "review-bot"
    event.get.side_effect = [
        MagicMock(
            json=lambda: [
                {"id": 1, "state": "APPROVED", "body": review_pr.REVIEW_MARKER, "user": {"login": "review-bot"}},
                {"id": 2, "state": "COMMENTED", "body": review_pr.REVIEW_MARKER, "user": {"login": "review-bot"}},
                {"id": 3, "state": "APPROVED", "body": "Human review", "user": {"login": "human"}},
                {"id": 6, "state": "COMMENTED", "body": "Other automation", "user": {"login": "review-bot"}},
            ]
        ),
        MagicMock(
            json=lambda: [
                {"id": 4, "pull_request_review_id": 1, "user": {"login": "review-bot"}},
                {"id": 5, "pull_request_review_id": 6, "user": {"login": "review-bot"}},
            ]
        ),
    ]

    review_pr.clear_previous_review(event)

    event.put.assert_called_once_with(
        "https://api.github.com/repos/org/repo/pulls/7/reviews/1/dismissals",
        json={"message": "Superseded by new review"},
        hard=True,
    )
    event.delete.assert_called_once_with(
        "https://api.github.com/repos/org/repo/pulls/comments/4",
        hard=True,
    )


def test_incomplete_review_evidence_cannot_approve():
    """Test unavailable or truncated diffs produce comments rather than approvals."""
    event = MagicMock()
    event.repository = "org/repo"
    event.pr = {"number": 7}
    event.get_pr_head_sha.return_value = "abc"

    error = review_pr.generate_pr_review("org/repo", "ERROR: UNABLE TO RETRIEVE DIFF.", "PR", "", event, "abc")
    review_pr.post_review_summary(event, error)
    assert event.post.call_args.kwargs["json"]["event"] == "COMMENT"

    review_pr.post_review_summary(event, {"head_sha": "abc", "summary": "LGTM", "comments": [], "diff_truncated": True})
    assert event.post.call_args.kwargs["json"]["event"] == "COMMENT"

    binary = "diff --git a/image.png b/image.png\nBinary files a/image.png and b/image.png differ"
    binary_review = review_pr.generate_pr_review("org/repo", binary, "PR", "", event, "abc")
    review_pr.post_review_summary(event, binary_review)
    assert event.post.call_args.kwargs["json"]["event"] == "COMMENT"

    with pytest.raises(KeyError):
        review_pr.post_review_summary(event, {"summary": "stale result", "comments": []})

    review_pr.post_review_summary(
        event, {"head_sha": "abc", "summary": "All changed files were skipped", "comments": []}
    )
    assert event.post.call_args.kwargs["json"]["event"] == "COMMENT"


def test_review_agent_tools_read_pr_head_via_api(tmp_path, monkeypatch):
    """Test review tools serve PR-head content via the GitHub API regardless of local checkout."""
    monkeypatch.chdir(tmp_path)
    event = MagicMock()
    event.repository = "org/repo"
    event.headers = {"Authorization": "Bearer x"}
    file_response = MagicMock(status_code=200, text="import torch\ntorch.zeros(1)\n")
    missing_response = MagicMock(status_code=404)
    tree_response = MagicMock(status_code=200)
    tree_response.json.return_value = {
        "tree": [{"path": "tests/test_python.py", "type": "blob"}, {"path": "docs", "type": "tree"}]
    }

    def fake_get(url, **kwargs):
        if "/git/trees/" in url:
            return tree_response
        if "missing.py" in url:
            return missing_response
        return MagicMock(status_code=500) if "flaky.py" in url else file_response

    event.get.side_effect = fake_get

    _, handlers = review_pr.build_review_agent_tools({}, "", event, "a" * 40, local_checkout=False)

    excerpt = handlers["read_file"](path="tests/test_python.py", start_line=1, end_line=1)
    assert "1: import torch" in excerpt
    assert handlers["read_file"](path="missing.py", start_line=None, end_line=None).endswith(
        "does not exist at the PR head."
    )
    with pytest.raises(RuntimeError):  # transient API errors must not read as "file missing"
        handlers["read_file"](path="flaky.py", start_line=None, end_line=None)

    tree_response.status_code = 500
    with pytest.raises(RuntimeError, match="list_files failed: HTTP 500"):
        handlers["list_files"](path_glob=None)
    tree_response.status_code = 200
    assert handlers["list_files"](path_glob=None).splitlines() == ["tests/test_python.py"]


@patch("actions.review_pr._fetch_head_file")
def test_get_repo_guidelines_fetches_pr_head(mock_fetch):
    """Test guidelines are fetched from the PR head via the GitHub API."""
    mock_fetch.side_effect = lambda event, sha, path: "Be nice" if path == "AGENTS.md" else None
    section = review_pr.get_repo_guidelines("gpt-5.6-sol", event=MagicMock(), head_sha="abc")
    assert "AGENTS.md" in section and "Be nice" in section
    assert "CONTRIBUTING.md" not in section
    assert review_pr.get_repo_guidelines("gpt-5.6-sol", event=None, head_sha="abc") == ""


def test_review_agent_tools_can_list_and_read_changed_file_diffs():
    """Test PR diff tools let the agent inspect every changed file on demand."""
    diff = "\n".join(
        [
            "diff --git a/early.py b/early.py",
            "--- a/early.py",
            "+++ b/early.py",
            "@@ -1 +1 @@",
            "-old = True",
            "+old = False",
            "diff --git a/nested/late.py b/nested/late.py",
            "--- a/nested/late.py",
            "+++ b/nested/late.py",
            "@@ -10 +10 @@",
            "-value = 1",
            "+value = 2",
        ]
    )
    diff_files, augmented_diff = review_pr.parse_diff_files(diff)
    _, handlers = review_pr.build_review_agent_tools(diff_files, augmented_diff)

    changed_files = handlers["list_changed_files"](path_glob=None)
    assert "early.py (+1/-1)" in changed_files
    assert "nested/late.py (+1/-1)" in changed_files
    assert handlers["list_changed_files"](path_glob="nested/**") == "nested/late.py (+1/-1)"
    late_diff = handlers["read_diff"](path="nested/late.py", start_line=None, end_line=None)
    assert "R   10 +value = 2" in late_diff
    assert "L   10 -value = 1" in late_diff
