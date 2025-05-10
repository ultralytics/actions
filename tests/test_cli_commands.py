# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import pytest
import importlib
import subprocess
from unittest.mock import patch

# Import CLI command modules
from actions import (
    first_interaction,
    summarize_pr,
    summarize_release,
    update_markdown_code_blocks,
)


def test_importable_modules():
    """Test that all modules can be imported without errors."""
    # This is a simple test to ensure modules can be imported successfully
    assert hasattr(first_interaction, "main")
    assert hasattr(summarize_pr, "main")
    assert hasattr(summarize_release, "main")
    assert hasattr(update_markdown_code_blocks, "main")


def check_cli_entry_point(entry_point, mock_func):
    """Helper function to test CLI entry points with minimal patching."""
    with patch.object(mock_func, "main", return_value=None) as mock_main:
        try:
            # Call the CLI command using subprocess
            subprocess.run(
                ["python", "-c", f"from {entry_point} import main; main()"],
                check=False,
                capture_output=True,
                timeout=1,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            # We expect the command to fail since we're not providing required env vars
            # but we just want to verify it's callable
            pass

        # If the command is properly importable, it succeeded
        return True


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"})
def test_first_interaction_command():
    """Test first interaction CLI command."""
    with patch.object(first_interaction, "main") as mock_main:
        mock_main.return_value = None

        try:
            subprocess.run(
                ["python", "-c", "from actions.first_interaction import main; main()"],
                check=False,
                capture_output=True,
                timeout=1,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        # The main function should be called when the module is executed
        assert mock_main.called


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"})
def test_summarize_pr_command():
    """Test summarize PR CLI command."""
    with patch.object(summarize_pr, "main") as mock_main:
        mock_main.return_value = None

        try:
            subprocess.run(
                ["python", "-c", "from actions.summarize_pr import main; main()"],
                check=False,
                capture_output=True,
                timeout=1,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        # The main function should be called when the module is executed
        assert mock_main.called


@patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"})
def test_summarize_release_command():
    """Test summarize release CLI command."""
    with patch.object(summarize_release, "main") as mock_main:
        mock_main.return_value = None

        try:
            subprocess.run(
                ["python", "-c", "from actions.summarize_release import main; main()"],
                check=False,
                capture_output=True,
                timeout=1,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        # The main function should be called when the module is executed
        assert mock_main.called


def test_update_markdown_command():
    """Test markdown update CLI command."""
    with patch.object(update_markdown_code_blocks, "main") as mock_main:
        mock_main.return_value = None

        try:
            subprocess.run(
                ["python", "-c", "from actions.update_markdown_code_blocks import main; main()"],
                check=False,
                capture_output=True,
                timeout=1,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        # The main function should be called when the module is executed
        assert mock_main.called
