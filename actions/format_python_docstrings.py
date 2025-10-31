# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import argparse
import tokenize
from io import BytesIO
from pathlib import Path


def wrap_text(text: str, width: int, indent: int) -> list[str]:
    """Wrap text at width with indentation."""
    if len(" " * indent + text) <= width:
        return [" " * indent + text]

    words, lines, current, current_len = text.split(), [], [], indent
    for word in words:
        word_len = len(word) + (1 if current else 0)
        if current_len + word_len > width and current:
            lines.append(" " * indent + " ".join(current))
            current, current_len = [word], indent + len(word)
        else:
            current.append(word)
            current_len += word_len

    if current:
        lines.append(" " * indent + " ".join(current))
    return lines


def parse_sections(content: str) -> dict[str, list[tuple[str, int]]]:
    """Parse docstring into sections with text and relative indentation."""
    sections = {
        k: []
        for k in [
            "summary",
            "description",
            "Args",
            "Attributes",
            "Returns",
            "Yields",
            "Raises",
            "Examples",
            "Notes",
            "References",
        ]
    }
    current, base_indent = "summary", 0

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current == "summary" and sections["summary"]:
                current = "description"
            continue

        # Section header detection
        if stripped.endswith(":") and (section := stripped[:-1]) in sections:
            current, base_indent = section, len(line) - len(line.lstrip())
            continue

        # Store content with relative indentation
        sections[current].append((stripped, max(0, len(line) - len(line.lstrip()) - base_indent)))

    return sections


def build_section(
    lines: list[str],
    section_name: str,
    content: list[tuple[str, int]],
    indent: int,
    line_width: int,
    preserve: bool = False,
) -> None:
    """Build a docstring section with proper indentation."""
    if not content:
        return
    lines.extend(["", " " * indent + f"{section_name}:"])
    sec_indent = indent + 4
    for text, rel_indent in content:
        if preserve:
            lines.append(" " * (sec_indent + rel_indent) + text)
        else:
            lines.extend(wrap_text(text, line_width, sec_indent + rel_indent))


def build_docstring(sections: dict[str, list[tuple[str, int]]], indent: int, line_width: int) -> str:
    """Build formatted docstring from sections."""
    lines = ['"""']  # First line has no indent (replacement handles it)

    # Summary (always single paragraph)
    if sections["summary"]:
        lines.extend(wrap_text(" ".join(s for s, _ in sections["summary"]), line_width, indent))

    # Description
    if sections["description"]:
        lines.append("")
        for text, _ in sections["description"]:
            lines.extend(wrap_text(text, line_width, indent))

    # Structured sections with wrapping
    for section_name in ["Args", "Attributes", "Returns", "Yields", "Raises", "Notes"]:
        build_section(lines, section_name, sections[section_name], indent, line_width)

    # Examples (preserve formatting)
    build_section(lines, "Examples", sections["Examples"], indent, line_width, preserve=True)

    # References (preserve formatting)
    if sections["References"]:
        lines.extend(["", " " * indent + "References:"])
        for text, _ in sections["References"]:
            lines.append(" " * (indent + 4) + text)

    lines.append(" " * indent + '"""')
    return "\n".join(lines)


def format_docstring(docstring: str, indent: int, line_width: int) -> str:
    """Format docstring to Google-style with specified line width."""
    content = docstring.strip().strip('"""').strip("'''").strip()

    # Check if should remain single-line (considering full line length with indentation)
    total_len = indent + 6 + len(content)  # indent + """content"""
    is_simple = (
        total_len <= line_width
        and "\n" not in content
        and not any(s in content for s in ["Args:", "Returns:", "Examples:"])
    )

    if is_simple:
        if content and not content[0].isupper():
            content = content[0].upper() + content[1:]
        if content and not content.endswith("."):
            content += "."
        return f'"""{content}"""'  # No leading indent for single-line

    # Multi-line docstrings need full indentation
    return build_docstring(parse_sections(content), indent, line_width)


def format_python_file(content: str, line_width: int = 120) -> str:
    """Format all docstrings in Python file."""
    try:
        tokens = list(tokenize.tokenize(BytesIO(content.encode()).readline))
    except (tokenize.TokenError, UnicodeDecodeError):
        return content

    # Find docstrings and format them
    replacements = []
    for i, token in enumerate(tokens):
        if token.type != tokenize.STRING or (
            i > 0 and tokens[i - 1].type not in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL)
        ):
            continue
        # Skip raw/f-string/byte-string prefixes
        if any(token.string.startswith(p) for p in ('r"""', "r'''", 'f"""', "f'''", 'b"""', "b'''")):
            continue
        # Only process triple-quoted strings (actual docstrings)
        if not (token.string.startswith('"""') or token.string.startswith("'''")):
            continue

        formatted = format_docstring(token.string, token.start[1], line_width)
        if formatted.strip() != token.string.strip():
            replacements.append((token.start, token.end, formatted))

    # Apply replacements in reverse order
    lines = content.split("\n")
    for start, end, formatted in reversed(replacements):
        start_line, start_col = start[0] - 1, start[1]
        end_line, end_col = end[0] - 1, end[1]

        if start_line == end_line:
            lines[start_line] = lines[start_line][:start_col] + formatted + lines[start_line][end_col:]
        else:
            new_lines = formatted.split("\n")
            new_lines[0] = lines[start_line][:start_col] + new_lines[0]
            new_lines[-1] += lines[end_line][end_col:]
            lines[start_line : end_line + 1] = new_lines

    return "\n".join(lines)


def process_file(path: Path, line_width: int = 120, check: bool = False) -> bool:
    """Process file, return True if no changes needed."""
    if path.suffix != ".py":
        return True

    try:
        original = path.read_text()
        formatted = format_python_file(original, line_width)

        if check:
            return original == formatted

        if original != formatted:
            path.write_text(formatted)
            print(f"Formatted: {path}")
            return False

        return True
    except Exception as e:
        print(f"Error: {path}: {e}")
        return True


def main(*args, **kwargs):
    """CLI entry point for formatting Python docstrings."""
    parser = argparse.ArgumentParser(description="Format Python docstrings to Google-style")
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to format")
    parser.add_argument("--line-width", type=int, default=120, help="Maximum line width (default: 120)")
    parser.add_argument("--check", action="store_true", help="Check without writing changes")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into directories")
    args = parser.parse_args()

    # Collect files
    files = []
    for path in args.paths:
        if path.is_dir() and args.recursive:
            files.extend(path.rglob("*.py"))
        elif path.is_file():
            files.append(path)

    # Process files
    all_ok = all(process_file(f, args.line_width, args.check) for f in files)

    if args.check and not all_ok:
        exit(1)


if __name__ == "__main__":
    main()
