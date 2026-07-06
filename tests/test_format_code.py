# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from pathlib import Path
from unittest.mock import call, patch

from actions import format_code

ACTION_YML = Path(__file__).parents[1] / "action.yml"


def test_format_commands_match_action_yml():
    """Test packaged formatter commands stay aligned with the composite action steps."""
    text = ACTION_YML.read_text(encoding="utf-8")
    for arg in [*format_code.RUFF_CHECK[1:], *format_code.RUFF_FORMAT[1:], format_code.DOCSTRINGS[0]]:
        assert arg == "." or arg.replace("=", " ") in text, f"ruff arg not in action.yml: {arg}"
    for line in format_code.PRETTIER.strip().splitlines():
        assert line.strip() in text, f"prettier line not in action.yml: {line.strip()}"
    for arg in format_code.CODESPELL[1:]:
        assert arg == "*" or arg in text, f"codespell arg not in action.yml: {arg}"


@patch("actions.format_code.subprocess.run")
def test_format_main_runs_all_formatters(mock_run, monkeypatch):
    """Test format CLI runs every formatter by default and respects INPUTS_* opt-outs."""
    format_code.main()
    assert mock_run.call_args_list == [
        call(format_code.RUFF_CHECK, shell=False, check=True),
        call(format_code.RUFF_FORMAT, shell=False, check=True),
        call(format_code.DOCSTRINGS, shell=False, check=True),
        call(format_code.PRETTIER, shell=True, check=True),
        call(format_code.CODESPELL, shell=False, check=True),
    ]

    mock_run.reset_mock()
    monkeypatch.setenv("INPUTS_PYTHON", "false")
    monkeypatch.setenv("INPUTS_SPELLING", "false")
    format_code.main()
    assert mock_run.call_args_list == [call(format_code.PRETTIER, shell=True, check=True)]
