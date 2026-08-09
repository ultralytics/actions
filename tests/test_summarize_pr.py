# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.summarize_pr import generate_merge_message, generate_pr_summary, label_fixed_issues


@patch("actions.summarize_pr.get_response")
def test_generate_pr_summary(mock_get_response):
    """Test generating PR summary with expected formatting."""
    mock_get_response.return_value = "Test PR summary content"
    summary = generate_pr_summary("test/repo", "diff content")

    assert summary.startswith("## 🛠️ PR Summary")
    assert "Test PR summary content" in summary
    mock_get_response.assert_called_once()


@patch("actions.summarize_pr.get_response")
def test_generate_merge_message_requires_quote_and_pr_impact(mock_get_response):
    """Test merged PR comments retain the personalized quote and impact requirements."""
    mock_get_response.return_value = "Merged response with quote"

    message = generate_merge_message("Improved export reliability", "@testuser", "https://github.com/test/repo/pull/1")

    assert message == "Merged response with quote"
    prompt = mock_get_response.call_args.args[0][1]["content"]
    assert "exactly one short, accurately attributed inspirational quote" in prompt
    assert "concrete impact" in prompt
    assert "Improved export reliability" in prompt


def test_label_fixed_issues_posts_repository_neutral_comment():
    """Test merged-issue responses avoid language, package-manager, and branch assumptions."""
    event = MagicMock(repository="owner/swift-app")
    event.get_pr_contributors.return_value = (
        "@testuser",
        {
            "url": "https://github.com/owner/swift-app/pull/123",
            "title": "Fix launch crash",
            "closingIssuesReferences": {"nodes": [{"number": 7}]},
        },
    )

    summary = "## 🛠️ PR Summary\n\n### 🌟 Summary\nFixed launch handling.\n\n### 📊 Key Changes\n- Safer startup"
    assert label_fixed_issues(event, summary) == "@testuser"
    comment = event.post.call_args_list[1].kwargs["json"]["body"]
    assert "[merged pull request](https://github.com/owner/swift-app/pull/123)" in comment
    assert "documented workflow" in comment
    assert "Fixed launch handling." in comment
    assert all(term not in comment for term in ("pip", "PyPI", "@main"))
