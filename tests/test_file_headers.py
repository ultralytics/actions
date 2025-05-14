# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# tests/test_update_file_headers.py
"""Tests for the file headers update functionality."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from actions.update_file_headers import COMMENT_MAP, IGNORE_PATHS, update_file


def test_update_file_python():
    """Test updating Python file headers."""
    with TemporaryDirectory() as tmp_dir:
        # Create a test Python file
        test_file = Path(tmp_dir) / "test.py"
        test_file.write_text("print('Hello World')\n")

        # Update file
        result = update_file(test_file, "# ", None, None, "Ultralytics 🚀 Test Header")

        # Check results
        assert result is True
        content = test_file.read_text()
        assert content.startswith("# Ultralytics 🚀 Test Header\n\n")
        assert "print('Hello World')" in content


def test_update_file_cpp():
    """Test updating C++ file headers."""
    with TemporaryDirectory() as tmp_dir:
        # Create a test C++ file
        test_file = Path(tmp_dir) / "test.cpp"
        test_file.write_text("#include <iostream>\n\nint main() {\n    return 0;\n}\n")

        # Update file
        result = update_file(test_file, "// ", "/* ", " */", "Ultralytics 🚀 Test Header")

        # Check results
        assert result is True
        content = test_file.read_text()
        assert content.startswith("// Ultralytics 🚀 Test Header\n\n")
        assert "#include <iostream>" in content


def test_update_file_with_existing_header():
    """Test updating file with existing header."""
    with TemporaryDirectory() as tmp_dir:
        # Create a test file with existing header
        test_file = Path(tmp_dir) / "test.py"
        test_file.write_text("# Ultralytics 🚀 AGPL-3.0 License\n\ndef main():\n    pass\n")

        # Update file
        result = update_file(test_file, "# ", None, None, "Ultralytics 🚀 Test Header")

        # Check results
        assert result is True
        content = test_file.read_text()
        assert content.startswith("# Ultralytics 🚀 Test Header\n\n")
        assert "def main():" in content


def test_update_file_with_shebang():
    """Test updating file with shebang."""
    with TemporaryDirectory() as tmp_dir:
        # Create a test file with shebang
        test_file = Path(tmp_dir) / "test.py"
        test_file.write_text("#!/usr/bin/env python3\n\nprint('Hello World')\n")

        # Update file
        result = update_file(test_file, "# ", None, None, "Ultralytics 🚀 Test Header")

        # Check results
        assert result is True
        content = test_file.read_text()
        assert content.startswith("#!/usr/bin/env python3\n# Ultralytics 🚀 Test Header\n\n")
        assert "print('Hello World')" in content


def test_update_file_no_changes():
    """Test updating file with no changes needed."""
    with TemporaryDirectory() as tmp_dir:
        # Create a test file with correct header
        test_file = Path(tmp_dir) / "test.py"
        test_file.write_text("# Ultralytics 🚀 Test Header\n\nprint('Hello World')\n")

        # Update file
        result = update_file(test_file, "# ", None, None, "Ultralytics 🚀 Test Header")

        # Check results
        assert result is False  # No changes made


def test_comment_map_coverage():
    """Test that all supported file extensions have defined comment styles."""
    # Check for a few key extensions
    assert ".py" in COMMENT_MAP
    assert ".cpp" in COMMENT_MAP
    assert ".js" in COMMENT_MAP
    assert ".html" in COMMENT_MAP

    # Check comment style format
    for ext, (prefix, block_start, block_end) in COMMENT_MAP.items():
        assert isinstance(ext, str)
        assert prefix is None or isinstance(prefix, str)
        assert block_start is None or isinstance(block_start, str)
        assert block_end is None or isinstance(block_end, str)


def test_ignore_paths():
    """Test that the ignore paths list exists and contains expected entries."""
    assert isinstance(IGNORE_PATHS, set)
    assert ".git" in IGNORE_PATHS
    assert "__pycache__" in IGNORE_PATHS


@patch("actions.update_file_headers.Path")
def test_main_function(mock_path):
    """Test the main function with mocked Path."""
    # Mock repository checks
    mock_event = MagicMock()
    mock_event.repository = "ultralytics/actions"
    mock_event.is_repo_private.return_value = False

    # Mock Path.cwd() and Path.rglob()
    mock_cwd = MagicMock()
    mock_path.cwd.return_value = mock_cwd

    # Mock some test files
    test_files = [MagicMock() for _ in range(3)]

    # Setup return paths for .py files
    for i, test_file in enumerate(test_files):
        test_file.relative_to.return_value = f"test{i}.py"
        # Mock __str__ to be used in any() checks
        test_file.__str__.return_value = f"/path/to/test{i}.py"

    # Setup the rglob to return our test files
    mock_cwd.rglob.return_value = test_files

    # Patch update_file to return True (indicating changes made)
    with patch("actions.update_file_headers.update_file", return_value=True):
        from actions.update_file_headers import main

        # Call the main function
        main(event=mock_event)

        # Check that rglob was called for each extension
        assert mock_cwd.rglob.call_count >= 1
