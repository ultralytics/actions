# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import patch

from actions.summarize_pr import generate_issue_comment, generate_merge_message, generate_pr_summary


@patch("actions.summarize_pr.get_response")
def test_generate_pr_summary(mock_get_response):
    """Test generating PR summary with expected formatting."""
    mock_get_response.return_value = "Test PR summary content"
    summary = generate_pr_summary("test/repo", "diff content")

    assert summary.startswith("## 🛠️ PR Summary")
    assert "Test PR summary content" in summary
    mock_get_response.assert_called_once()


@patch("actions.summarize_pr.get_response")
def test_generate_merge_message(mock_get_response):
    """Test generating merge thank you messages."""
    mock_get_response.return_value = "Thank you for your contribution!"

    message = generate_merge_message(
        pr_summary="Feature implementation", pr_credit="@testuser", pr_url="https://github.com/test/repo/pull/1"
    )

    assert message == "Thank you for your contribution!"
    mock_get_response.assert_called_once()


@patch("actions.summarize_pr.get_response")
def test_generate_issue_comment(mock_get_response):
    """Test generating issue comments about PR fixes."""
    mock_get_response.return_value = "This issue is fixed in PR #123"

    for pr_url in ("https://github.com/owner/repo/pull/123", "https://api.github.com/repos/owner/repo/pulls/123"):
        comment = generate_issue_comment(
            pr_url=pr_url,
            pr_summary="Fixed bug",
            pr_credit="@testuser",
            pr_title="Bug fix PR",
        )

        assert comment == "This issue is fixed in PR #123"
        prompt = mock_get_response.call_args[0][0][1]["content"]
        assert "pip install -U repo>=VERSION" in prompt
        assert "pip install git+https://github.com/owner/repo.git@main" in prompt

    assert mock_get_response.call_count == 2
