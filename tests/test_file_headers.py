# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, mock_open, patch

from actions.update_markdown_code_blocks import (
    add_indentation,
    extract_code_blocks,
    format_bash_with_prettier,
    format_code_with_ruff,
    generate_temp_filename,
    main,
    process_markdown_file,
    remove_indentation,
    update_markdown_file,
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


@patch("subprocess.run")
def test_format_code_with_ruff(mock_run):
    """Test formatting Python code with ruff."""
    mock_run.return_value = MagicMock()
    temp_dir = Path("temp")
    
    format_code_with_ruff(temp_dir)
    
    assert mock_run.call_count == 3  # ruff format, ruff check, docformatter
    # Verify first call is ruff format
    assert mock_run.call_args_list[0][0][0] == ["ruff", "format", "--line-length=120", str(temp_dir)]


@patch("subprocess.run")
def test_format_code_with_ruff_error(mock_run):
    """Test ruff formatting with subprocess errors."""
    mock_run.side_effect = Exception("Command failed")
    temp_dir = Path("temp")
    
    # Should not raise exception due to try/except blocks
    format_code_with_ruff(temp_dir)
    
    assert mock_run.call_count == 3


@patch("subprocess.run")
def test_format_bash_with_prettier(mock_run):
    """Test formatting bash code with prettier."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    temp_dir = Path("temp")
    
    format_bash_with_prettier(temp_dir)
    
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["shell"] is True


@patch("subprocess.run")
def test_format_bash_with_prettier_error(mock_run):
    """Test prettier formatting with errors."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Prettier error"
    mock_run.return_value = mock_result
    
    temp_dir = Path("temp")
    format_bash_with_prettier(temp_dir)
    
    mock_run.assert_called_once()


@patch("builtins.open", new_callable=mock_open)
def test_update_markdown_file(mock_file):
    """Test updating markdown files with formatted code."""
    mock_file.return_value.read.return_value = "formatted code"
    
    file_path = Path("test.md")
    markdown_content = "```python\noriginal code\n```"
    temp_files = [(0, "original code", Path("temp.py"), "python")]
    
    update_markdown_file(file_path, markdown_content, temp_files)
    
    # Verify file operations
    assert mock_file.call_count >= 2  # Read temp file, write markdown file


@patch("shutil.rmtree")
@patch("actions.update_markdown_code_blocks.format_bash_with_prettier")
@patch("actions.update_markdown_code_blocks.format_code_with_ruff")
@patch("actions.update_markdown_code_blocks.update_markdown_file")
@patch("actions.update_markdown_code_blocks.process_markdown_file")
@patch("pathlib.Path.rglob")
@patch("pathlib.Path.mkdir")
def test_main(mock_mkdir, mock_rglob, mock_process, mock_update, mock_ruff, mock_prettier, mock_rmtree):
    """Test main function execution."""
    # Mock markdown files
    mock_files = [Path("test1.md"), Path("test2.md")]
    mock_rglob.return_value = mock_files
    
    # Mock process_markdown_file return values
    mock_process.side_effect = [
        ("content1", [(0, "code1", Path("temp1.py"), "python")]),
        ("content2", [(0, "code2", Path("temp2.sh"), "bash")])
    ]
    
    main(process_python=True, process_bash=True)
    
    # Verify directory operations
    mock_mkdir.assert_called_once_with(exist_ok=True)
    mock_rmtree.assert_called_once()
    
    # Verify processing calls
    assert mock_process.call_count == 2
    mock_ruff.assert_called_once()
    mock_prettier.assert_called_once()
    assert mock_update.call_count == 2


@patch("shutil.rmtree")
@patch("actions.update_markdown_code_blocks.format_code_with_ruff")
@patch("actions.update_markdown_code_blocks.process_markdown_file")
@patch("pathlib.Path.rglob")
@patch("pathlib.Path.mkdir")
def test_main_python_only(mock_mkdir, mock_rglob, mock_process, mock_ruff, mock_rmtree):
    """Test main function with Python processing only."""
    mock_files = [Path("test.md")]
    mock_rglob.return_value = mock_files
    mock_process.return_value = ("content", [(0, "code", Path("temp.py"), "python")])
    
    main(process_python=True, process_bash=False)
    
    mock_ruff.assert_called_once()
    # format_bash_with_prettier should not be called
    with patch("actions.update_markdown_code_blocks.format_bash_with_prettier") as mock_prettier:
        mock_prettier.assert_not_called()
