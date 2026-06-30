# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions import dependabot


def response(status_code=200, text=""):
    """Create a minimal requests response mock."""
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    return r


def test_parse_runs_handles_block_and_inline_values():
    """Action manifest parsing should handle common YAML scalar styles."""
    assert dependabot.parse_runs('runs: {using: "node20", main: "dist/index.js"}') == ("node20", "dist/index.js")
    assert dependabot.parse_runs("runs:\n  using: 'node20' # runtime\n  main: dist/index.js # entry\n") == (
        "node20",
        "dist/index.js",
    )
    assert dependabot.parse_runs("runs:\n  using: composite\n  steps:\n    - with:\n        main: nested\n") == (
        "composite",
        None,
    )
    assert dependabot.parse_runs("inputs:\n  runs: ignored\nruns:\n  using: node20\n  main: dist/index.js\n") == (
        "node20",
        "dist/index.js",
    )


def test_reusable_workflow_detection():
    """Reusable workflows do not have action manifests and should skip action validation."""
    assert dependabot.is_reusable_workflow("owner/repo/.github/workflows/reuse.yml")
    assert dependabot.is_reusable_workflow("owner/repo/.github/workflows/reuse.yaml")
    assert not dependabot.is_reusable_workflow("owner/repo/sub/action")


@patch("actions.dependabot.requests.get")
def test_action_is_valid_checks_manifest_entrypoint(mock_get):
    """JavaScript actions are valid only when their declared entrypoint exists at the target ref."""
    mock_get.side_effect = [
        response(text="runs:\n  using: node20\n  main: dist/index.js\n"),
        response(200),
    ]

    assert dependabot.action_is_valid("owner/repo/path", "v1.2.3", "token")
    assert mock_get.call_args_list[-1].args[0].endswith("/repos/owner/repo/contents/path/dist/index.js?ref=v1.2.3")


@patch("actions.dependabot.requests.get")
def test_action_is_valid_rejects_missing_node_entrypoint(mock_get):
    """Missing JavaScript entrypoints should block broken action updates."""
    mock_get.side_effect = [
        response(text="runs:\n  using: node20\n  main: dist/index.js\n"),
        response(404),
    ]

    assert not dependabot.action_is_valid("owner/repo/path", "v1.2.3", "token")


@patch("actions.dependabot.requests.get")
def test_action_is_valid_accepts_composite_actions(mock_get):
    """Composite actions do not declare runs.main and only need a manifest."""
    mock_get.return_value = response(text="runs:\n  using: composite\n  steps: []\n")

    assert dependabot.action_is_valid("owner/repo/path", "v1.2.3", "token")
