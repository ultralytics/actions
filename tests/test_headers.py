# tests/test_dispatch_actions_extended.py
"""Extended tests for dispatch actions module."""

from unittest.mock import MagicMock, patch

import pytest

from actions.dispatch_actions import main


@patch("actions.dispatch_actions.Action")
def test_main_with_non_ci_keyword(mock_action_class):
    """Test main function with comment not containing the CI keyword."""
    # Configure mock
    mock_event = mock_action_class.return_value
    mock_event.event_name = "issue_comment"
    mock_event.event_data = {
        "action": "created",
        "issue": {"pull_request": {}},
        "comment": {"body": "Regular comment without keyword", "user": {"login": "testuser"}}
    }
    
    # Call the function
    main()
    
    # Verify the function exits early
    mock_event.toggle_eyes_reaction.assert_not_called()
    mock_event.is_org_member.assert_not_called()


@patch("actions.dispatch_actions.Action")
def test_main_with_non_org_member(mock_action_class):
    """Test main function with non-org member trying to use CI keyword."""
    # Configure mock
    mock_event = mock_action_class.return_value
    mock_event.event_name = "issue_comment"
    mock_event.event_data = {
        "action": "created",
        "issue": {"pull_request": {}},
        "comment": {
            "body": "Please run CI @ultralytics/run-ci", 
            "user": {"login": "external-user"}
        }
    }
    mock_event.is_org_member.return_value = False
    
    # Call the function
    main()
    
    # Check is_org_member was called but nothing else happened
    mock_event.is_org_member.assert_called_once_with("external-user")
    mock_event.toggle_eyes_reaction.assert_not_called()


@patch("actions.dispatch_actions.Action")
def test_main_with_backtick_quoted_keyword(mock_action_class):
    """Test main function with CI keyword in backticks (should be ignored)."""
    # Configure mock
    mock_event = mock_action_class.return_value
    mock_event.event_name = "issue_comment"
    mock_event.event_data = {
        "action": "created",
        "issue": {"pull_request": {}},
        "comment": {
            "body": "The keyword to run CI is `@ultralytics/run-ci` but I'm just mentioning it.",
            "user": {"login": "testuser"}
        }
    }
    
    # Call the function
    main()
    
    # Should be ignored due to backticks
    mock_event.is_org_member.assert_not_called()


@patch("actions.dispatch_actions.Action")
def test_main_with_non_issue_comment_event(mock_action_class):
    """Test main function with non-issue-comment event."""
    # Configure mock
    mock_event = mock_action_class.return_value
    mock_event.event_name = "push"
    
    # Call the function
    main()
    
    # Should exit early
    assert mock_event.event_data.get.call_count == 0


@patch("actions.dispatch_actions.Action")
def test_main_with_non_pr_issue(mock_action_class):
    """Test main function with comment on regular issue (not PR)."""
    # Configure mock
    mock_event = mock_action_class.return_value
    mock_event.event_name = "issue_comment"
    mock_event.event_data = {
        "action": "created",
        "issue": {},  # No pull_request key
        "comment": {
            "body": "Running CI @ultralytics/run-ci", 
            "user": {"login": "testuser"}
        }
    }
    
    # Call the function
    main()
    
    # Should exit early
    mock_event.is_org_member.assert_not_called()
