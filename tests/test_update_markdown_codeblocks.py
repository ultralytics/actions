# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import subprocess
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from actions.update_markdown_code_blocks import (
    add_indentation,
    extract_code_blocks,
    format_bash_with_prettier,
    generate_temp_filename,
    main,
    process_markdown_file,
    remove_indentation,
)


def prettier_sh_available():
    """Check whether prettier and prettier-plugin-sh are installed globally."""
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        return (Path(root) / "prettier-plugin-sh" / "lib" / "index.cjs").exists()
    except Exception:
        return False


def test_extract_code_blocks():
    """Test extracting code blocks from Markdown content."""
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
    """Test processing Markdown files."""
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


def test_mixed_indentation_block_not_extracted(tmp_path):
    """Test blocks with lines indented less than the fence are skipped instead of corrupted."""
    markdown = tmp_path / "example.md"
    markdown.write_text(
        """# Example

=== "Tab"

    ```bash
    hailortcli fw-control identify
Firmware Version: 4.23.0
    ```
""",
        encoding="utf-8",
    )

    markdown_content, temp_files = process_markdown_file(markdown, tmp_path)

    assert markdown_content is not None
    assert temp_files == []


def test_format_bash_skips_when_no_shell_files(tmp_path):
    """Test bash formatter skips Prettier when no shell snippets were extracted."""
    (tmp_path / "snippet.py").write_text("print('ok')", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        format_bash_with_prettier(tmp_path)

    mock_run.assert_not_called()


def test_format_bash_reports_skipped_snippets(tmp_path, capsys):
    """Test bash formatter reports parse failures as skips instead of errors."""
    (tmp_path / "good.sh").write_text('echo "hi"\n', encoding="utf-8")
    bad = tmp_path / "bad.sh"
    bad.write_text("Firmware Version: 4.23.0 (release,app,extended context switch buffer)\n", encoding="utf-8")
    prettier_result = subprocess.CompletedProcess(
        args="",
        returncode=2,
        stdout="good.sh 5ms\n",
        stderr=f"[error] {bad.name}: Error: a command can only contain words and redirects; encountered (\n",
    )

    with patch("subprocess.run", return_value=prettier_result):
        format_bash_with_prettier(tmp_path)

    output = capsys.readouterr().out
    assert "ERROR" not in output
    assert "1 formatted, 1 skipped" in output


def test_main_skips_symlinked_markdown(tmp_path):
    """Test Markdown formatter skips symlinks to avoid formatting the same content twice."""
    target = tmp_path / "AGENTS.md"
    target.write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").symlink_to(target)

    with patch("actions.update_markdown_code_blocks.process_markdown_file", return_value=("", [])) as mock_process:
        main(root_dir=tmp_path, process_python=False, process_bash=False)

    mock_process.assert_called_once()
    assert mock_process.call_args.args[0] == target


@pytest.mark.skipif(not prettier_sh_available(), reason="prettier-plugin-sh not installed")
def test_main_formats_valid_bash_and_skips_output_fences(tmp_path, capsys, monkeypatch):
    """Test valid bash fences are formatted while terminal-output fences are left unchanged."""
    monkeypatch.chdir(tmp_path)  # main() creates its temp dir in cwd
    markdown = tmp_path / "example.md"
    markdown.write_text(
        """# Example

```bash
pip install   ultralytics
```

```bash
Firmware Version: 4.23.0 (release,app,extended context switch buffer)
```
""",
        encoding="utf-8",
    )

    main(root_dir=tmp_path, process_python=False)

    content = markdown.read_text(encoding="utf-8")
    assert "pip install ultralytics" in content
    assert "Firmware Version: 4.23.0 (release,app,extended context switch buffer)" in content
    output = capsys.readouterr().out
    assert "ERROR running prettier-plugin-sh" not in output
    assert "1 formatted, 1 skipped" in output


def test_main_real_files():
    """Test main function on actual repository Markdown files."""
    # Run main on current directory which contains README.md and other Markdown files
    # This provides real-world test coverage of the entire pipeline
    main(process_python=True, process_bash=True, verbose=False)
