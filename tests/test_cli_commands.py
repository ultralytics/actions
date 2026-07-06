# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# Import CLI command modules
from actions import (
    first_interaction,
    format_code,
    format_python_docstrings,
    summarize_pr,
    summarize_release,
    update_markdown_code_blocks,
)


def test_importable_modules():
    """Test that all modules can be imported without errors."""
    # This is a simple test to ensure modules can be imported successfully
    assert hasattr(first_interaction, "main")
    assert hasattr(format_code, "main")
    assert hasattr(summarize_pr, "main")
    assert hasattr(summarize_release, "main")
    assert hasattr(update_markdown_code_blocks, "main")


def test_docstring_formatter_keeps_simple_docstrings_single_line():
    """Test simple docstrings stay single-line to match Ruff D200 fixes."""
    text = "Make the live fp32 EMA genuinely non-finite while the model stays finite (sticky-NaN on a finite-loss run)."

    assert format_python_docstrings.format_docstring(text, 8, 120, '"""', "") == f'"""{text}"""'


def test_docstring_formatter_preserves_identifier_first_words():
    """Test that code identifiers, dotted names, and URLs are not capitalized as first words."""
    for text in (
        "process_mask/process_mask_native/scale_masks must handle 0 detections without crashing.",
        "np.array inputs are converted to tensors.",
        "https://ultralytics.com hosts the docs.",
        "iOS builds are not supported.",
    ):
        assert format_python_docstrings.format_docstring(text, 8, 120, '"""', "") == f'"""{text}"""'
