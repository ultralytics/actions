# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.summarize_release import (
    create_github_release,
    generate_release_summary,
    get_prs_between_tags,
    get_release_diff,
)


def test_get_release_diff():
    """Test retrieving diff between tags."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"
    mock_event.headers_diff = {"Accept": "application/vnd.github.v3.diff"}

    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "diff content"
    mock_event.get.return_value = mock_response

    diff = get_release_diff(mock_event, "v1.0.0", "v1.1.0")

    assert diff == "diff content"
    mock_event.get.assert_called_once_with(
        "https://api.github.com/repos/test/repo/compare/v1.0.0...v1.1.0", headers=mock_event.headers_diff
    )


def test_get_prs_between_tags():
    """Test retrieving PRs between tags."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    # Mock compare response
    mock_compare_response = MagicMock()
    mock_compare_response.json.return_value = {
        "commits": [{"commit": {"message": "Fix bug #123"}}, {"commit": {"message": "Add feature #456"}}]
    }

    # Mock PR responses
    mock_pr1_response = MagicMock()
    mock_pr1_response.status_code = 200
    mock_pr1_response.json.return_value = {
        "number": 123,
        "title": "Fix bug",
        "body": "Fixes a bug",
        "user": {"login": "user1"},
        "html_url": "https://github.com/test/repo/pull/123",
        "merged_at": "2023-01-01T12:00:00Z",
    }

    mock_pr2_response = MagicMock()
    mock_pr2_response.status_code = 200
    mock_pr2_response.json.return_value = {
        "number": 456,
        "title": "Add feature",
        "body": "Adds a new feature",
        "user": {"login": "user2"},
        "html_url": "https://github.com/test/repo/pull/456",
        "merged_at": "2023-01-02T12:00:00Z",
    }

    # Set up get method to return different responses
    mock_event.get.side_effect = [mock_compare_response, mock_pr1_response, mock_pr2_response]

    # Use patch to skip the sleep
    with patch("time.sleep"):
        prs = get_prs_between_tags(mock_event, "v1.0.0", "v1.1.0")

    assert len(prs) == 2
    assert prs[0]["number"] == 123
    assert prs[1]["number"] == 456


@patch("actions.summarize_release.get_completion")
def test_generate_release_summary(mock_get_completion):
    """Test generating release summary."""
    mock_get_completion.return_value = "Release summary content"

    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    # Create test data with matching author for new contributor
    test_prs = [
        {
            "number": 123,
            "title": "Fix bug",
            "body": "Fixes a bug",
            "author": "newuser",  # Match the contributor name
            "html_url": "https://github.com/test/repo/pull/123",
            "merged_at": "2023-01-01T12:00:00Z",
        }
    ]

    # Mock new contributors function
    with patch("actions.summarize_release.get_new_contributors", return_value=["newuser"]):
        summary = generate_release_summary(
            event=mock_event, diff="diff content", prs=test_prs, latest_tag="v1.1.0", previous_tag="v1.0.0"
        )

    assert "Release summary content" in summary
    assert "What's Changed" in summary
    assert "https://github.com/test/repo/compare/v1.0.0...v1.1.0" in summary
    mock_get_completion.assert_called_once()


def test_create_github_release():
    """Test creating GitHub release."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    create_github_release(event=mock_event, tag_name="v1.1.0", name="Version 1.1.0", body="Release notes")

    mock_event.post.assert_called_once_with(
        "https://api.github.com/repos/test/repo/releases",
        json={
            "tag_name": "v1.1.0",
            "name": "Version 1.1.0",
            "body": "Release notes",
            "draft": False,
            "prerelease": False,
        },
    )
