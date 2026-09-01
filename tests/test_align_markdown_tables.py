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


def test_display_width_emoji_sequences():
    """Test joined emoji sequences count as one width-2 emoji, matching Prettier 3.8.5."""
    assert display_width("👩‍💻") == 2  # ZWJ sequence
    assert display_width("🇺🇸") == 2  # regional indicator flag pair
    assert display_width("👍🏽") == 2  # skin-tone modifier
    assert display_width("1️⃣") == 2  # keycap sequence


def test_display_width_variation_selector():
    """Test U+FE0F upgrades a narrow char to emoji width 2 while the bare char stays 1, matching Prettier."""
    assert display_width("❤️") == 2
    assert display_width("❤") == 1
    assert display_width("™️") == 2
    assert display_width("☀️") == 2
    assert display_width("→") == 1
    assert display_width("e\u0301") == 1  # e + combining accent U+0301


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
    content = '=== "Tab"\n\n    | Left | Center | Right |\n    |:-----|:------:|------:|\n    | a | b | c |\n'
    aligned = (
        '=== "Tab"\n\n    | Left | Center | Right |\n    | :--- | :----: | ----: |\n    | a    |   b    |     c |\n'
    )
    assert align_tables_in_markdown(content) == aligned


def test_ignores_top_level_tables():
    """Test tables indented under 4 spaces are left for Prettier."""
    content = "| Top | Level |\n|---|---|\n| a | b |\n"
    assert align_tables_in_markdown(content) == content


def test_ignores_indented_code_blocks():
    """Test table-looking content in a root-level indented code block stays untouched (it renders as code)."""
    content = "paragraph\n\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n"
    assert align_tables_in_markdown(content) == content
    at_file_start = "\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n"  # no context line above at all
    assert align_tables_in_markdown(at_file_start) == at_file_start


def test_ignores_code_block_inside_container():
    """Test an indented code block inside an admonition (extra 4 spaces) stays untouched."""
    content = "!!! note\n    text\n\n        | a | b |\n        |---|---|\n        | 1 | 2 |\n"
    assert align_tables_in_markdown(content) == content


def test_ignores_fenced_code_blocks():
    """Test table-looking content inside fenced code blocks stays untouched."""
    content = "```\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n```\n"
    assert align_tables_in_markdown(content) == content


def test_ignores_nested_shorter_fences():
    """Test a shorter fence run inside a longer fence does not close it."""
    content = "````\n```\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n````\n"
    assert align_tables_in_markdown(content) == content


def test_fence_closer_rejects_info_string():
    """Test a fence line carrying an info string does not close the block."""
    content = "```\n```python\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n```\n"
    assert align_tables_in_markdown(content) == content


def test_closing_fence_allows_extra_indent():
    """Test a closing fence indented up to 3 spaces beyond the opener still closes it."""
    content = "!!! note\n    ```\n    code\n       ```\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n"
    aligned = "!!! note\n    ```\n    code\n       ```\n    | a   | b   |\n    | --- | --- |\n    | 1   | 2   |\n"
    assert align_tables_in_markdown(content) == aligned


def test_table_directly_under_tab_marker():
    """Test a table starting immediately after a tab marker (no blank line) is aligned."""
    content = '=== "Tab"\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n'
    aligned = '=== "Tab"\n    | a   | b   |\n    | --- | --- |\n    | 1   | 2   |\n'
    assert align_tables_in_markdown(content) == aligned


def test_ignores_setext_heading():
    """Test a setext heading underline (=== with no title) is not treated as a tab marker."""
    content = "Title\n===\n\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n"
    assert align_tables_in_markdown(content) == content


def test_ignores_marker_inside_indented_code_block():
    """Test an indented marker-looking line in a root code block does not make its rows a table."""
    content = "paragraph\n\n    !!! note\n        | a | b |\n        |---|---|\n        | 1 | 2 |\n"
    assert align_tables_in_markdown(content) == content


def test_root_fence_closer_limited_to_three_spaces():
    """Test a root-level fence is not closed by a closer indented more than 3 spaces."""
    content = "  ```\n     ```\n!!! note\n\n    | a | b |\n    |---|---|\n    | 1 | 2 |\n"
    assert align_tables_in_markdown(content) == content  # fence never closed, table stays code content


def test_display_width_flag_pairs():
    """Test adjacent flag pairs count separately and a lone regional indicator stays narrow, per Prettier."""
    assert display_width("🇺🇸") == 2
    assert display_width("🇺🇸🇨🇦") == 4
    assert display_width("🇺") == 1


def test_ignores_malformed_tables():
    """Test rows with inconsistent cell counts or no delimiter row stay untouched."""
    ragged = "!!! note\n\n    | a | b |\n    |---|---|\n    | 1 |\n"
    assert align_tables_in_markdown(ragged) == ragged
    no_delimiter = "!!! note\n\n    | a | b |\n    | 1 | 2 |\n    | 3 | 4 |\n"
    assert align_tables_in_markdown(no_delimiter) == no_delimiter


def test_nested_tables_with_different_indents():
    """Test tables nested at different container levels are aligned independently."""
    content = (
        '!!! note\n\n    | a |\n    |---|\n    | 1 |\n\n    === "Tab"\n\n        | bb |\n        |---|\n        | 2 |\n'
    )
    aligned = '!!! note\n\n    | a   |\n    | --- |\n    | 1   |\n\n    === "Tab"\n\n        | bb  |\n        | --- |\n        | 2   |\n'
    assert align_tables_in_markdown(content) == aligned


def test_deeper_rows_after_table_are_code():
    """Test rows indented deeper than a table with no intervening marker are treated as code."""
    content = "!!! note\n\n    | a |\n    |---|\n    | 1 |\n        | bb |\n        |---|\n        | 2 |\n"
    aligned = "!!! note\n\n    | a   |\n    | --- |\n    | 1   |\n        | bb |\n        |---|\n        | 2 |\n"
    assert align_tables_in_markdown(content) == aligned


def test_table_at_end_of_file():
    """Test a table ending at EOF without a trailing newline is still aligned."""
    content = "!!! note\n\n    | a | b |\n    |---|---|\n    | 1 | 2 |"
    aligned = "!!! note\n\n    | a   | b   |\n    | --- | --- |\n    | 1   | 2   |"
    assert align_tables_in_markdown(content) == aligned


def test_process_file(tmp_path, capsys):
    """Test process_file rewrites only files whose tables changed."""
    file = tmp_path / "test.md"
    file.write_text(INDENTED_TABLE, encoding="utf-8")
    assert process_file(file) is True
    assert file.read_text(encoding="utf-8") == INDENTED_TABLE_ALIGNED
    assert process_file(file) is False


def test_process_file_error(tmp_path, capsys):
    """Test process_file reports errors and returns False for unreadable files."""
    assert process_file(tmp_path / "missing.md") is False
    assert "Error processing file" in capsys.readouterr().out


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
