# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# Import CLI command modules
from actions import (
    first_interaction,
    format_python_docstrings,
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


def test_docstring_formatter_keeps_simple_docstrings_single_line():
    """Test simple docstrings stay single-line to match Ruff D200 fixes."""
    text = "Make the live fp32 EMA genuinely non-finite while the model stays finite (sticky-NaN on a finite-loss run)."

    assert format_python_docstrings.format_docstring(text, 8, 120, '"""', "") == f'"""{text}"""'
