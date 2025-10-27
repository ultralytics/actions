# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from datetime import datetime
from unittest.mock import MagicMock, patch

from actions.dispatch_actions import (
    RUN_CI_KEYWORD,
    get_pr_branch,
    main,
    trigger_and_get_workflow_info,
    update_comment,
)


def test_get_pr_branch():
    """Test getting PR branch name."""
    mock_event = MagicMock()
    mock_event.event_data = {"issue": {"number": 123}}
    mock_event.get_repo_data.return_value = {
        "head": {"ref": "feature-branch", "repo": {"id": 1}},
        "base": {"repo": {"id": 1}},
    }

    branch, temp_branch = get_pr_branch(mock_event)

    assert branch == "feature-branch"
    assert temp_branch is None
    mock_event.get_repo_data.assert_called_once_with("pulls/123")


def test_get_pr_branch_fork():
    """Test getting PR branch name for fork PRs."""
    mock_event = MagicMock()
    mock_event.event_data = {"issue": {"number": 456}}
    mock_event.repository = "base/repo"
    mock_event.get_repo_data.return_value = {
        "head": {"ref": "fork-branch", "sha": "abc123", "repo": {"id": 2, "full_name": "fork/repo"}},
        "base": {"repo": {"id": 1}},
    }

    with patch("time.time", return_value=1234567.890):
        with patch("subprocess.run") as mock_run:
            with patch("os.environ.get", return_value="test-token"):
                branch, temp_branch = get_pr_branch(mock_event)

    assert branch == "temp-ci-456-1234567890"
    assert temp_branch == "temp-ci-456-1234567890"
    # Verify git commands were called
    assert mock_run.call_count == 4  # clone, remote add, fetch, push


def test_trigger_and_get_workflow_info():
    """Test triggering workflows and getting info."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    # Mock the workflow and runs responses separately
    workflow_response = MagicMock()
    workflow_response.status_code = 200
    workflow_response.json.return_value = {"name": "CI Workflow"}

    runs_response = MagicMock()
    runs_response.status_code = 200
    runs_response.json.return_value = {
        "workflow_runs": [{"html_url": "https://github.com/test/repo/actions/runs/123", "run_number": 42}]
    }

    # Set up get method to return different responses for different URLs
    def get_side_effect(url):
        if "workflows/ci.yml" in url and "runs" not in url:
            return workflow_response
        elif "workflows/ci.yml/runs" in url:
            return runs_response
        # Return default response for unexpected URLs
        default = MagicMock()
        default.status_code = 404
        return default

    mock_event.get.side_effect = get_side_effect

    # Use patch to skip time.sleep and limit to one workflow
    with patch("time.sleep"), patch("actions.dispatch_actions.WORKFLOW_FILES", ["ci.yml"]):
        results = trigger_and_get_workflow_info(mock_event, "feature-branch")

    # Check results
    assert len(results) == 1
    assert results[0]["name"] == "CI Workflow"
    assert results[0]["run_number"] == 42


def test_trigger_and_get_workflow_info_with_temp_branch():
    """Test that temp branches are deleted after triggering workflows."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"

    workflow_response = MagicMock()
    workflow_response.status_code = 200
    workflow_response.json.return_value = {"name": "CI Workflow"}

    runs_response = MagicMock()
    runs_response.status_code = 200
    runs_response.json.return_value = {"workflow_runs": [{"html_url": "https://example.com", "run_number": 1}]}

    def get_side_effect(url):
        if "workflows/ci.yml" in url and "runs" not in url:
            return workflow_response
        elif "runs" in url:
            return runs_response
        default = MagicMock()
        default.status_code = 404
        return default

    mock_event.get.side_effect = get_side_effect

    with patch("time.sleep"):
        with patch("actions.dispatch_actions.WORKFLOW_FILES", ["ci.yml"]):
            trigger_and_get_workflow_info(mock_event, "temp-ci-123-456", temp_branch="temp-ci-123-456")

    # Verify temp branch was deleted
    mock_event.delete.assert_called_once_with("https://api.github.com/repos/test/repo/git/refs/heads/temp-ci-123-456")


def test_update_comment_function():
    """Test updating comment with workflow info."""
    mock_event = MagicMock()
    mock_event.repository = "test/repo"
    mock_event.event_data = {"comment": {"id": 456}}

    comment_body = f"Run tests please {RUN_CI_KEYWORD}"
    triggered_actions = [
        {
            "name": "CI Workflow",
            "file": "ci.yml",
            "url": "https://github.com/test/repo/actions/workflows/ci.yml",
            "run_number": 42,
        }
    ]

    # Mock datetime to have a consistent timestamp
    with patch("actions.dispatch_actions.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        # Call without capturing return value
        update_comment(mock_event, comment_body, triggered_actions, "feature-branch")

    # Check that patch was called with expected content
    mock_event.patch.assert_called_once()

    # Verify key content in the comment body
    args, kwargs = mock_event.patch.call_args
    assert "https://api.github.com/repos/test/repo/issues/comments/456" in args[0]
    assert "Actions Trigger" in kwargs["json"]["body"]
    assert "CI Workflow" in kwargs["json"]["body"]
    assert "2023-01-01 12:00:00 UTC" in kwargs["json"]["body"]


def test_main_triggers_workflows():
    """Test main function when comment contains trigger keyword."""
    with patch("actions.dispatch_actions.Action") as MockAction:
        # Configure mock
        mock_event = MockAction.return_value
        mock_event.event_name = "issue_comment"
        mock_event.repository = "test/repo"
        mock_event.event_data = {
            "action": "created",
            "issue": {"pull_request": {}},
            "comment": {"body": f"Please run CI {RUN_CI_KEYWORD}", "user": {"login": "testuser"}, "id": 789},
        }
        mock_event.is_org_member.return_value = True

        # Create minimal patches for the functions called by main
        with patch("actions.dispatch_actions.get_pr_branch") as mock_get_branch:
            with patch("actions.dispatch_actions.trigger_and_get_workflow_info") as mock_trigger:
                with patch("actions.dispatch_actions.update_comment"):
                    # Set return values
                    mock_get_branch.return_value = ("feature-branch", None)
                    mock_trigger.return_value = [{"name": "CI", "file": "ci.yml", "url": "url", "run_number": 1}]

                    # Call the function
                    main()

        # Verify main component calls were made
        mock_event.is_org_member.assert_called_once_with("testuser")
        mock_get_branch.assert_called_once()
        mock_trigger.assert_called_once()


def test_main_skips_non_pr_comments():
    """Test main function skips non-PR comments."""
    with patch("actions.dispatch_actions.Action") as MockAction:
        # Configure mock
        mock_event = MockAction.return_value
        mock_event.event_name = "issue_comment"
        mock_event.event_data = {
            "action": "created",
            "issue": {},  # No pull_request key
            "comment": {"body": f"Please run CI {RUN_CI_KEYWORD}", "user": {"login": "testuser"}},
        }

        main()

        # Verify toggle_eyes_reaction was not called
        mock_event.toggle_eyes_reaction.assert_not_called()
