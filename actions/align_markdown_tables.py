# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

# Prettier aligns top-level pipe tables but parses lines indented 4+ spaces as code blocks, so tables inside
# MkDocs admonitions (!!!) and tabs (===) stay unformatted; this aligns exactly those tables in Prettier's style
TABLE_ROW = re.compile(r"^( {4,})\|(.*)$")
DELIMITER_CELL = re.compile(r"^:?-+:?$")
FENCE = re.compile(r"^( *)(`{3,}|~{3,})")


def display_width(text: str) -> int:
    """Return the rendered width of a string, counting wide chars (CJK, emoji) as 2 and zero-width marks as 0."""
    width = 0
    for char in text:
        if unicodedata.category(char) in ("Mn", "Me", "Cf"):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def split_row(body: str) -> list[str]:
    """Split a pipe-table row body into trimmed cell strings, honoring escaped pipes."""
    cells = re.split(r"(?<!\\)\|", body)
    if cells and cells[-1].strip() == "":
        cells.pop()  # trailing pipe
    return [cell.strip() for cell in cells]


def pad_cell(content: str, width: int, align: str) -> str:
    """Pad cell content to a display width following the column alignment, as Prettier does."""
    pad = width - display_width(content)
    if align == "right":
        return " " * pad + content
    if align == "center":
        left = pad // 2
        return " " * left + content + " " * (pad - left)
    return content + " " * pad


def align_table(lines: list[str]) -> list[str]:
    """Rebuild one table (indented row strings) with uniform Prettier-style padding, or return it unchanged."""
    indent = TABLE_ROW.match(lines[0]).group(1)
    rows = [split_row(TABLE_ROW.match(line).group(2)) for line in lines]
    if not (
        len(rows) >= 3
        and rows[1]
        and all(DELIMITER_CELL.match(cell) for cell in rows[1])
        and all(len(row) == len(rows[0]) for row in rows)
    ):
        return lines  # not a well-formed table (no header/delimiter/body or ragged rows); leave untouched

    aligns = []
    for cell in rows[1]:
        left, right = cell.startswith(":"), cell.endswith(":")
        aligns.append("center" if left and right else "left" if left else "right" if right else "")
    widths = [max(3, max(display_width(row[i]) for j, row in enumerate(rows) if j != 1)) for i in range(len(rows[0]))]
    delimiters = [
        ":" + "-" * (width - 2) + ":"
        if align == "center"
        else ":" + "-" * (width - 1)
        if align == "left"
        else "-" * (width - 1) + ":"
        if align == "right"
        else "-" * width
        for width, align in zip(widths, aligns)
    ]

    result = []
    for i, row in enumerate(rows):
        cells = (
            delimiters if i == 1 else [pad_cell(cell, width, align) for cell, width, align in zip(row, widths, aligns)]
        )
        result.append(f"{indent}| " + " | ".join(cells) + " |")
    return result


def align_tables_in_markdown(content: str) -> str:
    """Align all pipe tables indented 4+ spaces in a Markdown string, leaving fenced code blocks untouched."""
    out, table, table_indent, fence = [], [], None, None
    for line in content.split("\n"):
        fence_match = FENCE.match(line)
        if fence is None and fence_match:
            fence = fence_match
        elif (
            fence
            and fence_match
            and fence_match.group(1) == fence.group(1)
            and fence_match.group(2)[0] == fence.group(2)[0]
        ):
            fence = None
        row = TABLE_ROW.match(line) if fence is None else None
        if row and table and row.group(1) != table_indent:
            out.extend(align_table(table))
            table = []
        if row:
            table_indent = row.group(1)
            table.append(line)
            continue
        if table:
            out.extend(align_table(table))
            table = []
        out.append(line)
    if table:
        out.extend(align_table(table))
    return "\n".join(out)


def process_file(file_path: Path) -> bool:
    """Align tables in one Markdown file, rewriting it only if changed. Returns True if the file was updated."""
    try:
        content = file_path.read_text(encoding="utf-8")
        aligned = align_tables_in_markdown(content)
        if aligned != content:
            file_path.write_text(aligned, encoding="utf-8")
            print(f"Aligned tables in {file_path} ✅")
            return True
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
    return False


def main() -> None:
    """Align Markdown pipe tables in the given files/directories (default: current directory recursively)."""
    paths = [Path(arg) for arg in sys.argv[1:]] or [Path.cwd()]
    for path in paths:
        files = [path] if path.is_file() else sorted(f for f in path.rglob("*.md") if not f.is_symlink())
        for file in files:
            process_file(file)


if __name__ == "__main__":
    main()
