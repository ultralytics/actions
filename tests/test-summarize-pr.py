# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.summarize_pr import (
    generate_issue_comment,
    generate_merge_message,
    generate_pr_summary,
    update_pr_description,
)


@patch("actions.summarize_pr.get_completion")
def test_generate_pr_summary(mock_get_completion):
    """Test generating PR summary with expected formatting."""
    mock_get_completion.return_value = "Test PR summary content"
    summary = generate_pr_summary("test/repo", "diff content")

    assert summary.startswith("## 🛠️ PR Summary")
    assert "Test PR summary content" in summary
    mock_get_completion.assert_called_once()


@patch("actions.summarize_pr.get_completion")
def test_generate_merge_message(mock_get_completion):
    """Test generating merge thank you messages."""
    mock_get_completion.return_value = "Thank you for your contribution!"

    message = generate_merge_message(
        pr_summary="Feature implementation", pr_credit="@testuser", pr_url="https://github.com/test/repo/pull/1"
    )

    assert message == "Thank you for your contribution!"
    mock_get_completion.assert_called_once()


@patch("actions.summarize_pr.get_completion")
def test_generate_issue_comment(mock_get_completion):
    """Test generating issue comments about PR fixes."""
    mock_get_completion.return_value = "This issue is fixed in PR #123"

    comment = generate_issue_comment(
        pr_url="https://api.github.com/repos/owner/repo/pulls/123",
        pr_summary="Fixed bug",
        pr_credit="@testuser",
        pr_title="Bug fix PR",
    )

    assert comment == "This issue is fixed in PR #123"
    mock_get_completion.assert_called_once()


def test_update_pr_description():
    """Test updating PR description with summary."""
    # Mock Action class
    mock_event = MagicMock()
    mock_event.repository = "test/repo"
    mock_event.pr = {"number": 123}

    # Mock response for get request
    mock_response = MagicMock()
    mock_response.json.return_value = {"body": "Original description"}
    mock_event.get.return_value = mock_response

    # Test updating description
    update_pr_description(mock_event, "## 🛠️ PR Summary\nNew summary")

    # Verify patch was called with correct parameters
    mock_event.patch.assert_called_once()
    args, kwargs = mock_event.patch.call_args
    assert args[0] == "https://api.github.com/repos/test/repo/pulls/123"
    assert "Original description" in kwargs["json"]["body"]
    assert "## 🛠️ PR Summary\nNew summary" in kwargs["json"]["body"]
