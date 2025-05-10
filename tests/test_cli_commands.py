# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

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
