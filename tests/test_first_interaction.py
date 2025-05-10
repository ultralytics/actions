# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.first_interaction import (
    create_alert_label,
    get_event_content,
    get_first_interaction_response,
    get_relevant_labels,
)


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


@patch("actions.first_interaction.get_completion")
def test_get_relevant_labels(mock_get_completion):
    """Test getting relevant labels for an issue."""
    mock_get_completion.return_value = "bug, enhancement"

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
    mock_get_completion.assert_called_once()


@patch("actions.first_interaction.get_completion")
def test_get_first_interaction_response(mock_get_completion):
    """Test generating first interaction response."""
    mock_get_completion.return_value = "Thank you for your issue"

    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    response = get_first_interaction_response(
        event=mock_event, issue_type="issue", title="Test Issue", body="Issue description", username="testuser"
    )

    assert response == "Thank you for your issue"
    mock_get_completion.assert_called_once()


def test_create_alert_label():
    """Test creating Alert label."""
    mock_event = MagicMock()

    create_alert_label(mock_event)

    mock_event.post.assert_called_once()
    args, kwargs = mock_event.post.call_args
    assert "labels" in args[0]
    assert kwargs["json"]["name"] == "Alert"
    assert kwargs["json"]["color"] == "FF0000"
