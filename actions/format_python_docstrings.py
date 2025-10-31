# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import argparse
import ast
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


def parse_google_sections(content: str) -> dict[str, list[str]]:
    """Parse Google-style docstring sections."""
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
    current = "summary"

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current == "summary" and sections["summary"]:
                current = "description"
            continue

        # Check for section headers
        if stripped.endswith(":") and stripped[:-1] in sections:
            current = stripped[:-1]
            continue

        sections[current].append(line)

    return sections


def format_google_docstring(content: str, indent: int, line_width: int) -> str:
    """Format multi-line Google-style docstring."""
    sections = parse_google_sections(content)
    lines = ['"""']

    # Summary
    if sections["summary"]:
        summary = " ".join(line.strip() for line in sections["summary"])
        lines.extend(wrap_text(summary, line_width, indent))

    # Description
    if sections["description"]:
        lines.append("")
        for line in sections["description"]:
            if line.strip():
                lines.extend(wrap_text(line.strip(), line_width, indent))

    # Structured sections
    for section_name in ["Args", "Attributes", "Returns", "Yields", "Raises"]:
        if sections[section_name]:
            lines.extend(["", " " * indent + f"{section_name}:"])
            for line in sections[section_name]:
                # Preserve relative indentation for section content
                original_indent = len(line) - len(line.lstrip())
                if line.strip():
                    lines.extend(wrap_text(line.strip(), line_width, indent + 4 + max(0, original_indent - 4)))

    # Examples and Notes (preserve formatting)
    for section_name in ["Examples", "Notes"]:
        if sections[section_name]:
            lines.extend(["", " " * indent + f"{section_name}:"])
            for line in sections[section_name]:
                lines.append(line.rstrip())

    # References
    if sections["References"]:
        lines.extend(["", " " * indent + "References:"])
        for line in sections["References"]:
            lines.append(line.rstrip())

    lines.append(" " * indent + '"""')
    return "\n".join(lines)


def format_docstring(content: str, indent: int, line_width: int) -> str:
    """Format docstring to single-line or Google-style."""
    content = content.strip()

    # Check if should be single-line
    total_len = indent + 6 + len(content)
    is_single = (
        total_len <= line_width
        and "\n" not in content
        and not any(
            s in content
            for s in ["Args:", "Attributes:", "Returns:", "Yields:", "Raises:", "Examples:", "Notes:", "References:"]
        )
    )

    if is_single:
        if content and not content[0].isupper():
            content = content[0].upper() + content[1:]
        if content and not content.endswith("."):
            content += "."
        return f'"""{content}"""'

    # Multi-line Google-style
    return format_google_docstring(content, indent, line_width)


class DocstringFormatter(ast.NodeVisitor):
    """AST visitor to find and format docstrings."""

    def __init__(self, source_lines: list[str], line_width: int = 120):
        """Initialize formatter with source lines and line width."""
        self.source_lines = source_lines
        self.line_width = line_width
        self.replacements = []

    def visit_Module(self, node):
        """Visit module node."""
        self._process_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Visit class definition node."""
        self._process_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Visit function definition node."""
        self._process_docstring(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Visit async function definition node."""
        self._process_docstring(node)
        self.generic_visit(node)

    def _process_docstring(self, node):
        """Process docstring for a node."""
        docstring = ast.get_docstring(node, clean=False)
        if not docstring:
            return

        # Find the actual string node
        if not (isinstance(node, ast.Module) or (node.body and isinstance(node.body[0], ast.Expr))):
            return

        string_node = node.body[0] if isinstance(node, ast.Module) else node.body[0]
        if not isinstance(string_node, ast.Expr) or not isinstance(string_node.value, ast.Constant):
            return

        # Get position info
        start_line = string_node.lineno - 1
        end_line = string_node.end_lineno - 1
        start_col = string_node.col_offset

        # Extract original docstring from source
        if start_line == end_line:
            original = self.source_lines[start_line][start_col : string_node.end_col_offset]
        else:
            lines = [self.source_lines[start_line][start_col:]]
            lines.extend(self.source_lines[start_line + 1 : end_line])
            lines.append(self.source_lines[end_line][: string_node.end_col_offset])
            original = "\n".join(lines)

        # Format the docstring
        formatted = format_docstring(docstring, start_col, self.line_width)

        # Only record if changed
        if formatted.strip() != original.strip():
            self.replacements.append((start_line, end_line, start_col, string_node.end_col_offset, formatted))


def format_python_file(content: str, line_width: int = 120) -> str:
    """Format all docstrings in Python file using AST."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content

    source_lines = content.split("\n")
    formatter = DocstringFormatter(source_lines, line_width)
    formatter.visit(tree)

    # Apply replacements in reverse order
    for start_line, end_line, start_col, end_col, formatted in reversed(formatter.replacements):
        if start_line == end_line:
            source_lines[start_line] = (
                source_lines[start_line][:start_col] + formatted + source_lines[start_line][end_col:]
            )
        else:
            new_lines = formatted.split("\n")
            new_lines[0] = source_lines[start_line][:start_col] + new_lines[0]
            new_lines[-1] += source_lines[end_line][end_col:]
            source_lines[start_line : end_line + 1] = new_lines

    return "\n".join(source_lines)


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
