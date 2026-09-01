# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import sys

from actions.align_markdown_tables import (
    align_tables_in_markdown,
    display_width,
    main,
    pad_cell,
    process_file,
    split_row,
)

INDENTED_TABLE = """
!!! tip "Performance"

    === "YOLO26n"

        | Format        | Status | Size on disk (MB) | mAP50-95(B) |
        |---------------|--------|-------------------|-------------|
        | PyTorch       | ✅      | 5.3               | 0.4760       |
        | TorchScript   | ✅      | 9.8              | 0.4734      |
"""

INDENTED_TABLE_ALIGNED = """
!!! tip "Performance"

    === "YOLO26n"

        | Format      | Status | Size on disk (MB) | mAP50-95(B) |
        | ----------- | ------ | ----------------- | ----------- |
        | PyTorch     | ✅     | 5.3               | 0.4760      |
        | TorchScript | ✅     | 9.8               | 0.4734      |
"""


def test_display_width():
    """Test rendered width counts wide chars (emoji, CJK) as 2 and zero-width marks as 0."""
    assert display_width("abc") == 3
    assert display_width("✅") == 2
    assert display_width("✅️") == 2  # with variation selector U+FE0F
    assert display_width("中文") == 4


def test_split_row():
    """Test row splitting trims cells, drops the trailing pipe, and honors escaped pipes."""
    assert split_row(" a | b |") == ["a", "b"]
    assert split_row(" a | b") == ["a", "b"]
    assert split_row(r" a \| b | c |") == [r"a \| b", "c"]


def test_pad_cell():
    """Test cell padding follows the column alignment as Prettier does."""
    assert pad_cell("a", 3, "") == "a  "
    assert pad_cell("a", 3, "right") == "  a"
    assert pad_cell("a", 4, "center") == " a  "  # extra space goes right


def test_aligns_indented_table():
    """Test a misaligned MkDocs tab table is aligned in Prettier style, with emoji counted as width 2."""
    assert align_tables_in_markdown(INDENTED_TABLE) == INDENTED_TABLE_ALIGNED


def test_idempotent():
    """Test aligning an already aligned table produces no further changes."""
    assert align_tables_in_markdown(INDENTED_TABLE_ALIGNED) == INDENTED_TABLE_ALIGNED


def test_preserves_alignment_colons():
    """Test delimiter alignment colons are preserved and padded with dashes."""
    content = "    | Left | Center | Right |\n    |:-----|:------:|------:|\n    | a | b | c |\n"
    aligned = "    | Left | Center | Right |\n    | :--- | :----: | ----: |\n    | a    |   b    |     c |\n"
    assert align_tables_in_markdown(content) == aligned


def test_ignores_top_level_tables():
    """Test tables indented under 4 spaces are left for Prettier."""
    content = "| Top | Level |\n|---|---|\n| a | b |\n"
    assert align_tables_in_markdown(content) == content


def test_ignores_fenced_code_blocks():
    """Test table-looking content inside fenced code blocks stays untouched."""
    content = "```\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n```\n"
    assert align_tables_in_markdown(content) == content


def test_ignores_malformed_tables():
    """Test rows with inconsistent cell counts or no delimiter row stay untouched."""
    ragged = "    | a | b |\n    |---|---|\n    | 1 |\n"
    assert align_tables_in_markdown(ragged) == ragged
    no_delimiter = "    | a | b |\n    | 1 | 2 |\n    | 3 | 4 |\n"
    assert align_tables_in_markdown(no_delimiter) == no_delimiter


def test_adjacent_tables_with_different_indents():
    """Test consecutive tables at different indentation levels are aligned independently."""
    content = "    | a |\n    |---|\n    | 1 |\n\n        | bb |\n        |---|\n        | 2 |\n"
    aligned = "    | a   |\n    | --- |\n    | 1   |\n\n        | bb  |\n        | --- |\n        | 2   |\n"
    assert align_tables_in_markdown(content) == aligned


def test_process_file(tmp_path, capsys):
    """Test process_file rewrites only files whose tables changed."""
    file = tmp_path / "test.md"
    file.write_text(INDENTED_TABLE, encoding="utf-8")
    assert process_file(file) is True
    assert file.read_text(encoding="utf-8") == INDENTED_TABLE_ALIGNED
    assert process_file(file) is False


def test_main_with_file_and_dir_args(tmp_path, monkeypatch):
    """Test main() accepts file and directory paths."""
    file = tmp_path / "test.md"
    file.write_text(INDENTED_TABLE, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["align", str(file)])
    main()
    assert file.read_text(encoding="utf-8") == INDENTED_TABLE_ALIGNED

    subdir = tmp_path / "docs"
    subdir.mkdir()
    nested = subdir / "nested.md"
    nested.write_text(INDENTED_TABLE, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["align", str(tmp_path)])
    main()
    assert nested.read_text(encoding="utf-8") == INDENTED_TABLE_ALIGNED


def test_main_defaults_to_cwd(tmp_path, monkeypatch):
    """Test main() with no arguments processes the current directory recursively."""
    file = tmp_path / "test.md"
    file.write_text(INDENTED_TABLE, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["align"])
    monkeypatch.chdir(tmp_path)
    main()
    assert file.read_text(encoding="utf-8") == INDENTED_TABLE_ALIGNED
