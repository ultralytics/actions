# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import importlib
import re

import pytest

from actions import __version__
from actions.utils import (
    GITHUB_API_URL,
    GITHUB_GRAPHQL_URL,
    Action,
    allow_redirect,
    check_pypi_version,
    get_completion,
    remove_html_comments,
    ultralytics_actions_info,
)


def test_version_format():
    """Test that version follows the expected format."""
    version_pattern = re.compile(r"^\d+\.\d+\.\d+$")
    assert version_pattern.match(__version__), f"Version {__version__} does not match pattern"


def test_util_module_imports():
    """Test that all utilities can be imported from the utils module."""
    # Test the utils module exports
    assert GITHUB_API_URL.startswith("https://api.github.com")
    assert GITHUB_GRAPHQL_URL.startswith("https://api.github.com/graphql")

    # Check that Action class exists and is importable
    assert hasattr(Action, "__init__")
    assert hasattr(Action, "get")
    assert hasattr(Action, "post")

    # Check function imports
    assert callable(allow_redirect)
    assert callable(check_pypi_version)
    assert callable(get_completion)
    assert callable(remove_html_comments)
    assert callable(ultralytics_actions_info)


def test_all_modules_importable():
    """Test that all modules can be imported without errors."""
    modules = [
        "actions",
        "actions.utils",
        "actions.utils.common_utils",
        "actions.utils.github_utils",
        "actions.utils.openai_utils",
        "actions.first_interaction",
        "actions.summarize_pr",
        "actions.summarize_release",
        "actions.update_markdown_code_blocks",
        "actions.dispatch_actions",
    ]

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert module is not None, f"Failed to import {module_name}"


def test_cli_entry_points():
    """Test that CLI entry points are defined in pyproject.toml."""
    from pathlib import Path

    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    if not pyproject_path.exists():
        pytest.skip("pyproject.toml not found")

    content = pyproject_path.read_text()
    expected_names = [
        "ultralytics-actions-first-interaction",
        "ultralytics-actions-summarize-pr",
        "ultralytics-actions-summarize-release",
        "ultralytics-actions-update-markdown-code-blocks",
        "ultralytics-actions-info",
    ]

    for name in expected_names:
        assert name in content, f"Entry point {name} not found in pyproject.toml"
