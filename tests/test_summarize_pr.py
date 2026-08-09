# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.summarize_pr import generate_pr_summary, label_fixed_issues


@patch("actions.summarize_pr.get_response")
def test_generate_pr_summary(mock_get_response):
    """Test generating PR summary with expected formatting."""
    mock_get_response.return_value = "Test PR summary content"
    summary = generate_pr_summary("test/repo", "diff content")

    assert summary.startswith("## 🛠️ PR Summary")
    assert "Test PR summary content" in summary
    mock_get_response.assert_called_once()


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
    assert "[Fix launch crash](https://github.com/owner/swift-app/pull/123)" in comment
    assert "documented workflow" in comment
    assert "Fixed launch handling." in comment
    assert all(term not in comment for term in ("pip", "PyPI", "@main"))
