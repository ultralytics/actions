# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.summarize_release import (
    create_github_release,
    generate_release_summary,
    get_prs_between_tags,
    get_release_diff,
)
from actions.utils import Action


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

    assert diff == ("diff content", [])
    mock_event.get.assert_called_once_with(
        "https://api.github.com/repos/test/repo/compare/v1.0.0...v1.1.0", headers=mock_event.headers_diff
    )


def test_get_prs_between_tags():
    """Keep associated and referenced PRs in compare order when they merge in the same second."""
    event = Action(event_data={"repository": {"full_name": "test/repo"}}, verbose=False)
    commits = [
        {"sha": "abc", "commit": {"message": "Fix bug"}},
        {"sha": "def", "commit": {"message": "Release (Test/Repo#123), see other/repo#789"}},
    ]
    pr = {
        "number": 124,
        "title": "Fix bug",
        "body": "Fix",
        "user": {"login": "user1"},
        "html_url": "url",
        "merged_at": "2023-01-01T12:00:00Z",
        "merge_commit_sha": "abc",
    }
    responses = [
        MagicMock(status_code=200, json=lambda: {"commits": commits}),
        MagicMock(status_code=200, json=lambda: [pr]),
        MagicMock(status_code=403),
        MagicMock(status_code=200, json=lambda: dict(pr, number=123, merge_commit_sha="def", user=None)),
    ]
    with patch.object(event.session, "get", side_effect=responses) as get:
        prs = get_prs_between_tags(event, "v1.0.0", "v1.1.0")

    assert [(pr["number"], pr["author"]) for pr in prs] == [(124, "user1"), (123, "ghost")]
    assert get.call_args.args[0].endswith("/pulls/123")


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
            event=mock_event,
            diff=("diff content", ["generated/client.py"]),
            prs=test_prs,
            latest_tag="v1.1.0",
            previous_tag="v1.0.0",
        )

    assert "Release summary content" in summary
    assert "What's Changed" in summary
    assert "https://github.com/test/repo/compare/v1.0.0...v1.1.0" in summary
    assert "generated/client.py" in mock_get_response.call_args.args[0][1]["content"]
    mock_get_response.assert_called_once()


def test_create_github_release():
    """Test creating GitHub release."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"
    mock_event.post.return_value.status_code = 201

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
    mock_event.get.assert_not_called()


@patch("actions.summarize_release.time.sleep")
def test_create_github_release_retries_server_error(mock_sleep):
    """Test a 5xx release POST is retried and the release is verified when the retry reports a duplicate."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"
    mock_event.post.side_effect = [MagicMock(status_code=500), MagicMock(status_code=422)]

    create_github_release(event=mock_event, tag_name="v1.1.0", name="Version 1.1.0", body="Release notes")

    assert mock_event.post.call_count == 2
    mock_sleep.assert_called_once_with(30)
    mock_event.get.assert_called_once_with("https://api.github.com/repos/test/repo/releases/tags/v1.1.0", hard=True)
