# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from pathlib import Path
from unittest.mock import mock_open, patch

from actions.update_markdown_code_blocks import (
    add_indentation,
    extract_code_blocks,
    generate_temp_filename,
    process_markdown_file,
    remove_indentation,
)


def test_extract_code_blocks():
    """Test extracting code blocks from markdown content."""
    # Test with Python and Bash code blocks
    markdown_content = """
# Test Markdown

```python
def test():
    return True
```

And some bash code:

```bash
echo "Hello World"
```
"""
    code_blocks = extract_code_blocks(markdown_content)

    assert len(code_blocks["python"]) == 1
    assert code_blocks["python"][0][1] == "def test():\n    return True"

    assert len(code_blocks["bash"]) == 1
    assert code_blocks["bash"][0][1] == 'echo "Hello World"'


def test_remove_indentation():
    """Test removing indentation from code blocks."""
    code_block = "    line 1\n    line 2\n    line 3"
    result = remove_indentation(code_block, 4)

    assert result == "line 1\nline 2\nline 3"

    # Test with mixed indentation
    code_block = "    line 1\n  line 2\n    line 3"
    result = remove_indentation(code_block, 2)

    assert result == "  line 1\nline 2\n  line 3"


def test_add_indentation():
    """Test adding indentation to code blocks."""
    code_block = "line 1\nline 2\nline 3"
    result = add_indentation(code_block, 4)

    assert result == "    line 1\n    line 2\n    line 3"

    # Test with empty lines
    code_block = "line 1\n\nline 3"
    result = add_indentation(code_block, 2)

    assert result == "  line 1\n\n  line 3"


def test_generate_temp_filename():
    """Test generating temporary filenames."""
    file_path = Path("docs/guide.md")

    filename = generate_temp_filename(file_path, 0, "python")

    assert "guide_docs_p0_" in filename
    assert filename.endswith(".py")

    filename = generate_temp_filename(file_path, 1, "bash")

    assert "guide_docs_b1_" in filename
    assert filename.endswith(".sh")


@patch("pathlib.Path.read_text")
@patch("pathlib.Path.write_text")
@patch("builtins.open", new_callable=mock_open)
def test_process_markdown_file(mock_file, mock_write, mock_read_text):
    """Test processing markdown files."""
    mock_read_text.return_value = """
# Test

```python
def test():
    return True
```
"""

    file_path = Path("test.md")
    temp_dir = Path("temp")

    markdown_content, temp_files = process_markdown_file(file_path, temp_dir)

    assert markdown_content is not None
    assert len(temp_files) == 1
    assert temp_files[0][1] == "def test():\n    return True"
    mock_file.assert_called_once()
