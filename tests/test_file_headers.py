# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Tests for the file headers update functionality."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from actions.update_file_headers import COMMENT_MAP, IGNORE_PATHS, main, update_file


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


def test_main_real_files():
    """Test main function on actual repository files."""
    # Mock update_file to prevent actual file modifications during testing
    with patch("actions.update_file_headers.update_file", return_value=False) as mock_update:
        main()
        # Verify that update_file was called (indicates file processing occurred)
        assert mock_update.call_count > 0


def test_main_with_custom_header():
    """Test main function with custom header environment variable."""
    with patch("actions.update_file_headers.update_file", return_value=False):
        with patch("actions.update_file_headers.HEADER", "Custom Test Header"):
            with patch("actions.update_file_headers.Action") as mock_action:
                mock_event = mock_action.return_value
                mock_event.repository = "test/repo"
                main()
                mock_action.assert_called_once()
