# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import sys
from textwrap import indent

import pytest

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

TABLE = "    | a | b |\n    |---|---|\n    | 1 | 2 |\n"  # minimal 4-space-indented table
TABLE_ALIGNED = "    | a   | b   |\n    | --- | --- |\n    | 1   | 2   |\n"


@pytest.mark.parametrize(
    ("text", "width"),
    [
        ("abc", 3),
        ("\u2705", 2),  # ✅
        ("\u2705\ufe0f", 2),  # ✅ with variation selector
        ("中文", 4),
        ("\U0001f469\u200d\U0001f4bb", 2),  # 👩‍💻 ZWJ sequence
        ("\U0001f1fa\U0001f1f8", 2),  # 🇺🇸 flag pair
        ("\U0001f1fa\U0001f1f8\U0001f1e8\U0001f1e6", 4),  # 🇺🇸🇨🇦 adjacent flag pairs
        ("\U0001f1fa", 1),  # lone regional indicator
        ("\U0001f44d\U0001f3fd", 2),  # 👍🏽 skin-tone modifier
        ("\u270c\U0001f3fd", 2),  # ✌🏽 narrow emoji with skin-tone modifier
        ("1\ufe0f\u20e3", 2),  # 1️⃣ keycap sequence
        ("\u2764\ufe0f", 2),  # ❤️ VS16 upgrades narrow char to emoji width
        ("\u2764", 1),  # ❤ bare
        ("\u2122\ufe0f", 2),  # ™️
        ("\u2600\ufe0f", 2),  # ☀️
        ("→", 1),
        ("é", 1),  # e + combining accent U+0301
    ],
)
def test_display_width(text, width):
    """Test rendered widths match Prettier 3.8.5: wide chars and emoji sequences count 2, zero-width marks 0."""
    assert display_width(text) == width


@pytest.mark.parametrize(
    "content",
    [
        "| Top | Level |\n|---|---|\n| a | b |\n",  # top-level tables are Prettier's domain
        "paragraph\n\n" + TABLE,  # root-level indented code block
        "\n" + TABLE,  # indented rows at file start with no context above
        "!!! note\n    text\n\n" + indent(TABLE, "    "),  # indented code block inside an admonition
        "```\n" + TABLE + "```\n",  # fenced code block
        "````\n```\n" + TABLE + "````\n",  # shorter fence run inside a longer fence
        "```\n```python\n" + TABLE + "```\n",  # fence closer carrying an info string
        "  ```\n     ```\n!!! note\n\n" + TABLE,  # root fence closer indented over 3 spaces
        "Title\n===\n\n" + TABLE,  # setext heading underline is not a tab marker
        "Title\n===   \n\n" + TABLE,  # setext underline with trailing spaces is not a tab marker
        '=== "Unclosed tab\n\n' + TABLE,  # invalid tab marker without a closing quote
        "!!!\n\n" + TABLE,  # admonition marker without a type payload
        "!!!! note\n\n" + TABLE,  # invalid four-character admonition marker
        "paragraph\n\n    !!! note\n" + indent(TABLE, "    "),  # marker-looking line inside a code block
        "!!! note\n\n    | a | b |\n    |---|---|\n    | 1 |\n",  # ragged rows
        "!!! note\n\n    | a | b |\n    | 1 | 2 |\n    | 3 | 4 |\n",  # no delimiter row
    ],
    ids=[
        "top-level",
        "indented-code-block",
        "file-start",
        "code-inside-container",
        "fenced",
        "nested-shorter-fence",
        "info-string-closer",
        "over-indented-root-closer",
        "setext-heading",
        "setext-trailing-spaces",
        "unclosed-tab-title",
        "bare-admonition-marker",
        "invalid-admonition-marker",
        "marker-inside-code",
        "ragged-rows",
        "no-delimiter",
    ],
)
def test_untouched(content):
    """Test table-looking content that is code, malformed, or outside containers stays byte-identical."""
    assert align_tables_in_markdown(content) == content


def test_root_indented_fence_does_not_suppress_later_tables():
    """Test a 4-space fence-looking line at root is an indented code block, so later real tables still align."""
    content = "    ```\n    sample\n!!! note\n\n" + TABLE
    aligned = "    ```\n    sample\n!!! note\n\n" + TABLE_ALIGNED
    assert align_tables_in_markdown(content) == aligned


@pytest.mark.parametrize("marker", ['=== "Tab"', '===+ "Tab"', '===! "Tab"'])
def test_tab_marker_variants(marker):
    """Test PyMdown tab markers (plain, new-group ===+, alternate ===!) all qualify as containers."""
    content = marker + "\n" + TABLE
    aligned = marker + "\n" + TABLE_ALIGNED
    assert align_tables_in_markdown(content) == aligned


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


def test_closing_fence_allows_extra_indent():
    """Test a closing fence indented up to 3 spaces beyond the opener still closes it."""
    content = "!!! note\n    ```\n    code\n       ```\n" + TABLE
    aligned = "!!! note\n    ```\n    code\n       ```\n" + TABLE_ALIGNED
    assert align_tables_in_markdown(content) == aligned


def test_table_directly_under_tab_marker():
    """Test a table starting immediately after a tab marker (no blank line) is aligned."""
    content = '=== "Tab"\n' + TABLE
    aligned = '=== "Tab"\n' + TABLE_ALIGNED
    assert align_tables_in_markdown(content) == aligned


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
    content = "!!! note\n\n" + TABLE.rstrip("\n")
    aligned = "!!! note\n\n" + TABLE_ALIGNED.rstrip("\n")
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
