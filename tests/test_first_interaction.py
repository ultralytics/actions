# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions import review_pr
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


@patch("actions.review_pr.get_agent_response")
def test_generate_pr_review_uses_synchronous_response(mock_get_agent_response):
    """Test PR reviews avoid background polling for code diffs."""
    mock_get_agent_response.return_value = {"comments": [], "summary": "LGTM"}
    diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old = True
+old = False
"""

    review = review_pr.generate_pr_review("ultralytics/actions", diff, "Test PR", "")

    assert review["summary"] == "LGTM"
    mock_get_agent_response.assert_called_once()
    kwargs = mock_get_agent_response.call_args.kwargs
    assert "background" not in kwargs
    assert kwargs["tools"][0]["type"] == "web_search"
    assert "filters" not in kwargs["tools"][0]
    assert {tool.get("name") for tool in kwargs["tools"] if tool.get("type") == "function"} == {
        "list_files",
        "read_file",
        "search_repo",
    }
    assert kwargs["max_turns"] == review_pr.MAX_AGENT_TURNS
    assert kwargs["request_timeout"] == (30, 120)


def test_review_agent_tools_can_read_repo_but_not_outside(tmp_path, monkeypatch):
    """Test local review tools can inspect unchanged repo files without escaping the checkout."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "changed.py").write_text("target = True\n", encoding="utf-8")
    (tmp_path / "secret.py").write_text("secret = True\n", encoding="utf-8")
    (tmp_path / "patterns.py").write_text("literal = '(a+)+$'\n", encoding="utf-8")
    workflow = tmp_path / ".github" / "workflows" / "format.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("workflow = True\n", encoding="utf-8")
    outside = tmp_path.parent / "outside_secret.py"
    outside.write_text("outside_secret = True\n", encoding="utf-8")
    (tmp_path / "linked_secret.py").symlink_to(outside)
    (tmp_path / "linked_internal.py").symlink_to(tmp_path / "secret.py")

    _, handlers = review_pr.build_review_agent_tools()

    assert "target = True" in handlers["read_file"](path="changed.py", start_line=None, end_line=None)
    assert "secret = True" in handlers["read_file"](path="secret.py", start_line=None, end_line=None)
    assert "path must stay inside repository" in handlers["read_file"](
        path="linked_secret.py", start_line=None, end_line=None
    )
    listed_files = handlers["list_files"](path_glob=None).splitlines()
    assert "secret.py" in listed_files
    assert ".github/workflows/format.yml" in handlers["list_files"](path_glob=".github/**").splitlines()
    assert "secret.py:1:secret = True" in handlers["search_repo"](query="secret = True", path_glob=None)
    assert "No matches found." == handlers["search_repo"](query="secret.*True", path_glob=None)
    assert "patterns.py:1:literal = '(a+)+$'" in handlers["search_repo"](query="(a+)+$", path_glob=None)
    assert ".github/workflows/format.yml:1:workflow = True" in handlers["search_repo"](
        query="workflow = True", path_glob=".github/**"
    )
