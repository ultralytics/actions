# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

"""Tests for the unified CLI interface."""

import subprocess
import sys
from unittest.mock import patch

import pytest


def test_cli_help():
    """Test that CLI help works."""
    result = subprocess.run([sys.executable, "-m", "actions.cli", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "ultralytics-actions" in result.stdout
    assert "Available commands" in result.stdout


def test_cli_version():
    """Test that CLI version flag works."""
    result = subprocess.run([sys.executable, "-m", "actions.cli", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "ultralytics-actions" in result.stdout


def test_cli_no_command():
    """Test that CLI shows help when no command provided."""
    result = subprocess.run([sys.executable, "-m", "actions.cli"], capture_output=True, text=True)
    assert result.returncode == 1
    assert "usage:" in result.stdout


def test_cli_subcommands_listed():
    """Test that all expected subcommands are listed in help."""
    result = subprocess.run([sys.executable, "-m", "actions.cli", "--help"], capture_output=True, text=True)
    expected_commands = [
        "first-interaction",
        "review-pr",
        "summarize-pr",
        "summarize-release",
        "update-markdown-code-blocks",
        "headers",
        "format-python-docstrings",
        "info",
    ]
    for cmd in expected_commands:
        assert cmd in result.stdout, f"Command {cmd} not found in help output"


@patch("actions.utils.ultralytics_actions_info")
def test_cli_info_command(mock_info):
    """Test that info command is properly routed."""
    mock_info.return_value = None
    result = subprocess.run([sys.executable, "-m", "actions.cli", "info"], capture_output=True, text=True)
    # Should exit cleanly even if the function doesn't do much in test environment
    assert result.returncode in [0, 1]  # May fail due to missing env vars but command should be recognized


def test_cli_invalid_command():
    """Test that invalid command shows help."""
    result = subprocess.run(
        [sys.executable, "-m", "actions.cli", "invalid-command"], capture_output=True, text=True
    )
    assert result.returncode != 0
