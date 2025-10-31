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

    mock_event.get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"commits": [{"commit": {"message": "Fix bug #123"}}]}),
        MagicMock(
            status_code=200,
            json=lambda: {
                "number": 123,
                "title": "Fix bug",
                "body": "Fix",
                "user": {"login": "user1"},
                "html_url": "url",
                "merged_at": "2023-01-01T12:00:00Z",
            },
        ),
    ]

    with patch("time.sleep"):
        prs = get_prs_between_tags(mock_event, "v1.0.0", "v1.1.0")

    assert len(prs) == 1
    assert prs[0]["number"] == 123


def test_get_prs_between_tags_api_failure():
    """Test API failure returns empty list."""
    mock_event = MagicMock()
    mock_event.get.return_value = MagicMock(status_code=404)

    assert get_prs_between_tags(mock_event, "v1.0.0", "v1.1.0") == []


def test_get_prs_between_tags_missing_commits():
    """Test missing commits data returns empty list."""
    mock_event = MagicMock()
    mock_event.get.return_value = MagicMock(status_code=200, json=lambda: {"message": "No commits"})

    assert get_prs_between_tags(mock_event, "v1.0.0", "v1.1.0") == []


def test_get_prs_between_tags_empty_commits():
    """Test empty commits list returns empty list."""
    mock_event = MagicMock()
    mock_event.get.return_value = MagicMock(status_code=200, json=lambda: {"commits": []})

    with patch("time.sleep"):
        assert get_prs_between_tags(mock_event, "v1.0.0", "v1.1.0") == []


@patch("actions.summarize_release.get_response")
def test_generate_release_summary(mock_get_response):
    """Test generating release summary."""
    mock_get_response.return_value = "Release summary content"

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
    mock_get_response.assert_called_once()


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
