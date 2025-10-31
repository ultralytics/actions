# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import argparse
import ast
from pathlib import Path


def wrap_text(text: str, width: int, indent: int) -> list[str]:
    """Wrap text at width with indentation."""
    if not text.strip():
        return []
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


def count_balanced_parens(s: str) -> int:
    """Find position of closing paren that balances opening paren at start."""
    if not s.startswith("("):
        return -1
    depth = 0
    for i, char in enumerate(s):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def is_param_line(line: str) -> bool:
    """Check if line starts a parameter definition with proper bracket handling."""
    stripped = line.strip()
    if not stripped or ":" not in stripped:
        return False

    # Handle edge case of just ":" with no param name
    if stripped == ":":
        return False

    # Try to find balanced parentheses for type annotation
    if "(" in stripped:
        try:
            paren_start = stripped.index("(")
            # Find balanced closing paren
            closing_pos = count_balanced_parens(stripped[paren_start:])
            if closing_pos == -1:
                return False
            # After closing paren, should have colon
            after_paren = stripped[paren_start + closing_pos + 1 :].strip()
            return after_paren.startswith(":")
        except (ValueError, IndexError):
            return False
    else:
        # No parens - check for valid param pattern
        # Must have something before colon (param name or type in parens)
        colon_pos = stripped.find(":")
        if colon_pos == 0:
            return False
        return True


def format_args_section(lines: list[str], base_indent: int, line_width: int) -> list[str]:
    """Format Args/Returns/Yields section with proper Google-style indentation."""
    formatted = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Check if this is a parameter definition line
        if is_param_line(line):
            stripped = line.strip()

            # Collect continuation lines (including blank lines within param)
            continuation = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.strip():
                    # Blank line - could be end or within param
                    if j + 1 < len(lines) and lines[j + 1].strip() and not is_param_line(lines[j + 1]):
                        # Blank line within param description
                        continuation.append("")
                        j += 1
                    else:
                        # End of this param
                        break
                elif is_param_line(next_line):
                    # Next param
                    break
                else:
                    # Continuation line
                    continuation.append(next_line.strip())
                    j += 1

            # Split at first colon only (description may contain colons)
            if ":" in stripped:
                try:
                    colon_pos = stripped.index(":")
                    param_part = stripped[:colon_pos].strip()
                    desc_part = stripped[colon_pos + 1 :].strip()

                    # Handle edge case where param_part is empty
                    if not param_part:
                        formatted.extend(wrap_text(stripped, line_width, base_indent))
                        i = j
                        continue

                    # Combine description with continuations
                    full_desc = desc_part
                    if continuation:
                        full_desc += " " + " ".join(c for c in continuation if c)

                    # Try to fit on one line
                    one_line = f"{param_part}: {full_desc}" if full_desc else f"{param_part}:"
                    if len(" " * base_indent + one_line) <= line_width:
                        formatted.append(" " * base_indent + one_line)
                    else:
                        # Need to wrap - try to fit as much as possible on first line
                        first_line = " " * base_indent + param_part + ": "
                        remaining_space = line_width - len(first_line)

                        if not full_desc:
                            # No description, just param
                            formatted.append(first_line.rstrip())
                        else:
                            # Split description into words and fit as many as possible on first line
                            words = full_desc.split()
                            first_line_words = []
                            remaining_words = []

                            current_len = 0
                            for word in words:
                                word_len = len(word) + (1 if first_line_words else 0)
                                if current_len + word_len <= remaining_space:
                                    first_line_words.append(word)
                                    current_len += word_len
                                else:
                                    remaining_words.append(word)

                            # Build the formatted output
                            if first_line_words:
                                formatted.append(first_line + " ".join(first_line_words))
                                if remaining_words:
                                    # Wrap remaining words at continuation indent
                                    remaining_text = " ".join(remaining_words)
                                    wrapped = wrap_text(remaining_text, line_width, base_indent + 4)
                                    formatted.extend(wrapped)
                            else:
                                # Couldn't fit any words on first line (very long first word)
                                formatted.append(first_line.rstrip())
                                wrapped = wrap_text(full_desc, line_width, base_indent + 4)
                                formatted.extend(wrapped)

                    i = j
                except (ValueError, IndexError):
                    # Error handling - just format as-is
                    formatted.extend(wrap_text(stripped, line_width, base_indent))
                    i += 1
            else:
                # No colon found (shouldn't happen but handle it)
                formatted.extend(wrap_text(stripped, line_width, base_indent))
                i += 1
        else:
            # Content without colon pattern
            formatted.extend(wrap_text(line.strip(), line_width, base_indent))
            i += 1

    return formatted


def parse_google_sections(content: str) -> dict[str, list[str]]:
    """Parse Google-style docstring into sections."""
    sections = {
        k: []
        for k in [
            "summary",
            "description",
            "Args",
            "Attributes",
            "Methods",
            "Returns",
            "Yields",
            "Raises",
            "Examples",
            "Notes",
            "References",
        ]
    }
    current = "summary"
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Empty line handling
        if not stripped:
            if current == "summary" and sections["summary"]:
                current = "description"
            elif sections[current]:
                sections[current].append("")
            i += 1
            continue

        # Check for section headers (must be exact match, alone on line)
        if stripped.endswith(":") and len(stripped) > 1:
            potential_section = stripped[:-1]
            # Only treat as section if it's a known section AND line has no other content
            if potential_section in sections and stripped == potential_section + ":":
                current = potential_section
                i += 1
                continue

        sections[current].append(line)
        i += 1

    return sections


def format_google_docstring(content: str, indent: int, line_width: int) -> str:
    """Format multi-line Google-style docstring with proper indentation."""
    sections = parse_google_sections(content)
    lines = ['"""']

    # Summary (single paragraph, wrapped)
    if sections["summary"]:
        summary = " ".join(line.strip() for line in sections["summary"] if line.strip())
        if summary:
            lines.extend(wrap_text(summary, line_width, indent))

    # Description (preserve paragraph structure)
    if sections["description"]:
        desc_lines = sections["description"]
        if any(line.strip() for line in desc_lines):
            lines.append("")
            paragraph = []
            for line in desc_lines:
                if not line.strip():
                    if paragraph:
                        text = " ".join(paragraph)
                        lines.extend(wrap_text(text, line_width, indent))
                        paragraph = []
                        lines.append("")
                else:
                    paragraph.append(line.strip())
            if paragraph:
                text = " ".join(paragraph)
                lines.extend(wrap_text(text, line_width, indent))

            # Remove trailing blank lines from description
            while lines and lines[-1] == "":
                lines.pop()

    # Structured sections (Args, Attributes, Methods, Returns, Yields, Raises)
    for section_name in ["Args", "Attributes", "Methods", "Returns", "Yields", "Raises"]:
        if sections[section_name] and any(line.strip() for line in sections[section_name]):
            lines.append("")
            lines.append(" " * indent + f"{section_name}:")
            formatted = format_args_section(sections[section_name], indent + 4, line_width)
            if formatted:  # Only add if there's actual content
                lines.extend(formatted)
            else:
                # Remove the section header if no content
                lines.pop()
                if lines and lines[-1] == "":
                    lines.pop()

    # Examples/Notes/References (preserve formatting)
    for section_name in ["Examples", "Notes", "References"]:
        if sections[section_name] and any(line.strip() for line in sections[section_name]):
            lines.append("")
            lines.append(" " * indent + f"{section_name}:")
            for line in sections[section_name]:
                lines.append(line.rstrip())

    # Remove trailing empty lines
    while lines and lines[-1] == "":
        lines.pop()

    lines.append(" " * indent + '"""')
    return "\n".join(lines)


def format_docstring(content: str, indent: int, line_width: int) -> str:
    """Format docstring to single-line or Google-style."""
    if not content or not content.strip():
        return '""""""'  # Empty docstring

    content = content.strip()

    # Check if should be single-line
    total_len = indent + 6 + len(content)
    has_sections = any(
        s in content
        for s in [
            "Args:",
            "Attributes:",
            "Methods:",
            "Returns:",
            "Yields:",
            "Raises:",
            "Examples:",
            "Notes:",
            "References:",
        ]
    )
    is_single = total_len <= line_width and "\n" not in content and not has_sections

    if is_single:
        # Ensure proper capitalization and punctuation
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
        """Visit module node - skip module-level docstrings."""
        # Don't process module docstring, but visit children
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
        try:
            docstring = ast.get_docstring(node, clean=False)
            if not docstring:
                return

            # Find the string node - must be first statement
            if not node.body or not isinstance(node.body[0], ast.Expr):
                return

            string_node = node.body[0]
            if not isinstance(string_node.value, ast.Constant) or not isinstance(string_node.value.value, str):
                return

            # Get position
            start_line = string_node.lineno - 1
            end_line = string_node.end_lineno - 1
            start_col = string_node.col_offset
            end_col = string_node.end_col_offset

            # Validate indices
            if start_line < 0 or end_line >= len(self.source_lines):
                return

            # Extract original
            if start_line == end_line:
                original = self.source_lines[start_line][start_col:end_col]
            else:
                lines = [self.source_lines[start_line][start_col:]]
                lines.extend(self.source_lines[start_line + 1 : end_line])
                lines.append(self.source_lines[end_line][:end_col])
                original = "\n".join(lines)

            # Format
            formatted = format_docstring(docstring, start_col, self.line_width)

            # Record if changed
            if formatted.strip() != original.strip():
                self.replacements.append((start_line, end_line, start_col, end_col, formatted))

        except (IndexError, ValueError, AttributeError):
            # Skip any problematic docstrings
            return


def format_python_file(content: str, line_width: int = 120) -> str:
    """Format all docstrings in Python file using AST."""
    if not content.strip():
        return content

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content

    source_lines = content.split("\n")
    formatter = DocstringFormatter(source_lines, line_width)

    try:
        formatter.visit(tree)
    except Exception:
        # If visiting fails, return original content
        return content

    # Apply replacements in reverse order to maintain line numbers
    for start_line, end_line, start_col, end_col, formatted in reversed(formatter.replacements):
        try:
            if start_line == end_line:
                source_lines[start_line] = (
                    source_lines[start_line][:start_col] + formatted + source_lines[start_line][end_col:]
                )
            else:
                new_lines = formatted.split("\n")
                new_lines[0] = source_lines[start_line][:start_col] + new_lines[0]
                new_lines[-1] += source_lines[end_line][end_col:]
                source_lines[start_line : end_line + 1] = new_lines
        except IndexError:
            continue

    return "\n".join(source_lines)


def process_file(path: Path, line_width: int = 120, check: bool = False) -> bool:
    """Process file, return True if no changes needed."""
    if path.suffix != ".py":
        return True

    try:
        original = path.read_text(encoding="utf-8")
        formatted = format_python_file(original, line_width)

        if check:
            return original == formatted

        if original != formatted:
            path.write_text(formatted, encoding="utf-8")
            print(f"Formatted: {path}")
            return False

        return True
    except Exception as e:
        print(f"Error: {path}: {e}")
        return True


def main(*args, **kwargs):
    """CLI entry point for formatting Python docstrings."""
    parser = argparse.ArgumentParser(description="Format Python docstrings to Google-style")
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to recursively format")
    parser.add_argument("--line-width", type=int, default=120, help="Maximum line width (default: 120)")
    parser.add_argument("--check", action="store_true", help="Check without writing changes")
    args = parser.parse_args()

    # Collect files (automatically recurse into directories)
    files = []
    for path in args.paths:
        if path.is_dir():
            files.extend(path.rglob("*.py"))
        elif path.is_file():
            files.append(path)
        else:
            print(f"Warning: {path} not found")

    # Process files
    all_ok = all(process_file(f, args.line_width, args.check) for f in files)

    if args.check and not all_ok:
        exit(1)


if __name__ == "__main__":
    main()
