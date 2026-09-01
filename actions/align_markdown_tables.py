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
FENCE_OPEN = re.compile(r"^( *)(`{3,}|~{3,})")
FENCE_CLOSE = re.compile(r"^( *)(`{3,}|~{3,})[ \t]*$")  # closers cannot carry an info string
CONTAINER_MARKER = re.compile(r"^(?:!!!+|\?\?\?\+?|===)\s")  # MkDocs admonition or tab at a given indent


def display_width(text: str) -> int:
    """Return the rendered width of a string, counting wide chars (CJK, emoji) as 2 and zero-width marks as 0."""
    width, last, join_next, skip_next = 0, 0, False, False
    for i, char in enumerate(text):
        cp = ord(char)
        if skip_next:  # second half of a regional-indicator flag pair
            skip_next, last = False, 0
            continue
        if char == "\u200d":  # ZWJ joins the surrounding emoji into a single sequence
            join_next = True
            continue
        if cp in (0xFE0F, 0x20E3):  # emoji variation selector / enclosing keycap widen the previous char
            if last == 1:
                width, last = width + 1, 2
            continue
        if unicodedata.category(char) in ("Mn", "Me", "Cf"):
            continue
        # ZWJ-joined emoji and skin-tone modifiers add no width; a flag pair counts as one width-2 emoji
        if join_next or 0x1F3FB <= cp <= 0x1F3FF:
            last = 0
        elif 0x1F1E6 <= cp <= 0x1F1FF and i + 1 < len(text) and 0x1F1E6 <= ord(text[i + 1]) <= 0x1F1FF:
            width, last, skip_next = width + 2, 2, True
        else:
            last = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
            width += last
        join_next = False
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


def delimiter_cell(width: int, align: str) -> str:
    """Return a delimiter cell of dashes padded to a column width, with colons marking the alignment."""
    if align == "center":
        return ":" + "-" * (width - 2) + ":"
    if align == "left":
        return ":" + "-" * (width - 1)
    if align == "right":
        return "-" * (width - 1) + ":"
    return "-" * width


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
    delimiters = [delimiter_cell(width, align) for width, align in zip(widths, aligns)]

    result = []
    for i, row in enumerate(rows):
        cells = (
            delimiters if i == 1 else [pad_cell(cell, width, align) for cell, width, align in zip(row, widths, aligns)]
        )
        result.append(f"{indent}| " + " | ".join(cells) + " |")
    return result


def in_container(lines: list[str], end: int, indent: int) -> bool:
    """Return True if a table at the given indent sits inside a MkDocs tab/admonition, not an indented code block."""
    for i in range(end - 1, -1, -1):
        line = lines[i]
        if not line.strip():
            continue
        line_indent = len(line) - len(line.lstrip(" "))
        if line_indent >= indent:
            continue  # container content at the table's level, keep scanning
        # First dedent below the table decides: a marker exactly one level up means container content,
        # and the marker itself must sit at root or inside a valid container (not in an indented code block)
        return (
            line_indent == indent - 4
            and bool(CONTAINER_MARKER.match(line[line_indent:]))
            and (line_indent == 0 or in_container(lines, i, line_indent))
        )
    return False


def align_tables_in_markdown(content: str) -> str:
    """Align pipe tables inside MkDocs tab/admonition containers, leaving all code blocks untouched."""
    out, table, table_indent, fence = [], [], None, None

    def flush():
        """Emit the accumulated table, aligned only when inside a MkDocs container."""
        nonlocal table
        if table:
            out.extend(align_table(table) if in_container(out, len(out), len(table_indent)) else table)
            table = []

    for line in content.split("\n"):
        if fence is None:
            fence_match = FENCE_OPEN.match(line)
            if fence_match:
                indent, run = fence_match.groups()
                fence = (run[0], len(run), len(indent))
        else:
            fence_match = FENCE_CLOSE.match(line)
            # Closing fence: same marker char, run at least as long as the opener, and indent within 3 spaces of
            # the containing block (root-level fences sit at margin 0; container content approximates its margin)
            max_indent = fence[2] + 3 if fence[2] >= 4 else 3
            if (
                fence_match
                and fence_match.group(2)[0] == fence[0]
                and len(fence_match.group(2)) >= fence[1]
                and len(fence_match.group(1)) <= max_indent
            ):
                fence = None
        row = TABLE_ROW.match(line) if fence is None else None
        if row and table and row.group(1) != table_indent:
            flush()
        if row:
            table_indent = row.group(1)
            table.append(line)
            continue
        flush()
        out.append(line)
    flush()
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
