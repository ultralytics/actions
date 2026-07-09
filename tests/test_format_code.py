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


def test_action_yml_groups_close_on_exit():
    """Test every run step opens a log group that closes even when a command fails."""
    lines = ACTION_YML.read_text(encoding="utf-8").splitlines()
    run_lines = [i for i, line in enumerate(lines) if line.strip().startswith("run:")]

    assert run_lines
    for i in run_lines:
        assert lines[i].strip() == "run: |", f"line {i + 1}: run step must be a block opening a log group"
        assert lines[i + 1].strip().startswith('echo "::group::'), f"line {i + 2}: run step must open a log group"
        assert lines[i + 2].strip() == "trap 'echo \"::endgroup::\"' EXIT", f"line {i + 3}: missing EXIT trap"
    assert not any(line.strip() == 'echo "::endgroup::"' for line in lines)


def test_markdown_prettier_skips_symlinks():
    """Test Markdown formatting only targets regular files because Prettier rejects explicit symlink paths."""
    assert 'find . -name "*.md" -type f' in format_code.PRETTIER
    assert 'find ./docs -name "*.md" -type f' in format_code.PRETTIER


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
