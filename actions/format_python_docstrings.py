# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import ast
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

URLS = {"https", "http", "ftp"}
SECTIONS = (
    "Args",
    "Attributes",
    "Methods",
    "Returns",
    "Yields",
    "Raises",
    "Example",
    "Examples",
    "Notes",
    "References",
)
SECTION_ALIASES = {
    "Arguments": "Args",
    "Usage": "Examples",
    "Usage Example": "Examples",
    "Usage Examples": "Examples",
    "Example Usage": "Examples",
    "Example": "Examples",
    "Return": "Returns",
    "Note": "Notes",
    "Reference": "References",
}
LIST_RX = re.compile(r"""^(\s*)(?:[-*•]\s+|(?:\d+|[A-Za-z]+)[\.\)]\s+)""")
TABLE_RX = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE_RX = re.compile(r"^\s*[:\-\|\s]{3,}$")
TREE_CHARS = ("└", "├", "│", "─")

# Antipatterns for non-Google docstring styles
RST_FIELD_RX = re.compile(r"^\s*:(param|type|return|rtype|raises)\b", re.M)
EPYDOC_RX = re.compile(r"^\s*@(?:param|type|return|rtype|raise)\b", re.M)
NUMPY_UNDERLINE_SECTION_RX = re.compile(r"^\s*(Parameters|Returns|Yields|Raises|Notes|Examples)\n[-]{3,}\s*$", re.M)
GOOGLE_SECTION_RX = re.compile(
    r"^\s*(Args|Attributes|Methods|Returns|Yields|Raises|Example|Examples|Notes|References):\s*$", re.M
)
NON_GOOGLE = {"numpy", "rest", "epydoc"}

# Default directories to skip when discovering Python files
EXCLUDED_DIR_NAMES = {
    "venv",
    ".venv",
    "env",
    ".env",
    "build",
    "dist",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".git",
    "site-packages",
    ".eggs",
    "eggs",
    ".idea",
    ".vscode",
}


def wrap_words(words: list[str], width: int, indent: int, min_words_per_line: int = 1) -> list[str]:
    """Wrap words to width with indent; optionally avoid very short orphan lines."""
    pad = " " * indent
    if not words:
        return []
    lines: list[list[str]] = []
    cur: list[str] = []
    cur_len = indent
    for w in words:
        need = len(w) + (1 if cur else 0)
        if cur and cur_len + need > width:
            lines.append(cur)
            cur, cur_len = [w], indent + len(w)
        else:
            cur.append(w)
            cur_len += need
    if cur:
        lines.append(cur)
    if min_words_per_line > 1:
        i = 1
        while i < len(lines):
            if len(lines[i]) < min_words_per_line and len(lines[i - 1]) > 1:
                donor = lines[i - 1][-1]
                this_len = len(pad) + sum(len(x) for x in lines[i]) + (len(lines[i]) - 1)
                if this_len + (1 if lines[i] else 0) + len(donor) <= width:
                    lines[i - 1].pop()
                    lines[i].insert(0, donor)
                    if i > 1 and len(lines[i - 1]) == 1:
                        i -= 1
                        continue
            i += 1
    return [pad + " ".join(line) for line in lines]


def wrap_para(text: str, width: int, indent: int, min_words_per_line: int = 1) -> list[str]:
    """Wrap a paragraph string; orphan control via min_words_per_line."""
    if text := text.strip():
        return wrap_words(text.split(), width, indent, min_words_per_line)
    else:
        return []


def wrap_hanging(head: str, desc: str, width: int, cont_indent: int) -> list[str]:
    """Wrap 'head + desc' with hanging indent; ensure first continuation has ≥2 words."""
    room = width - len(head)
    words = desc.split()
    if not words:
        return [head.rstrip()]
    take, used = [], 0
    for w in words:
        need = len(w) + (1 if take else 0)
        if used + need <= room:
            take.append(w)
            used += need
        else:
            break
    out: list[str] = []
    if take:
        out.append(head + " ".join(take))
        rest = words[len(take) :]
    else:
        out.append(head.rstrip())
        rest = words
    out.extend(wrap_words(rest, width, cont_indent, min_words_per_line=2))
    return out


def is_list_item(s: str) -> bool:
    """Return True if s looks like a bullet/numbered list item."""
    return bool(LIST_RX.match(s.lstrip()))


def is_fence_line(s: str) -> bool:
    """Return True if s is a Markdown code-fence line."""
    t = s.lstrip()
    return t.startswith("```")


def is_table_like(s: str) -> bool:
    """Return True if s resembles a simple Markdown table or rule line."""
    return bool(TABLE_RX.match(s)) or bool(TABLE_RULE_RX.match(s))


def is_tree_like(s: str) -> bool:
    """Return True if s contains common ASCII tree characters."""
    return any(ch in s for ch in TREE_CHARS)


def is_indented_block_line(s: str) -> bool:
    """Return True if s looks like a deeply-indented preformatted block."""
    return bool(s.startswith("        ")) or s.startswith("\t")


def header_name(line: str) -> str | None:
    """Return canonical section header or None."""
    s = line.strip()
    if not s.endswith(":") or len(s) <= 1:
        return None
    name = s[:-1].strip()
    # Apply aliases to normalize section names
    name = SECTION_ALIASES.get(name, name)
    return name if name in SECTIONS else None


def add_header(lines: list[str], indent: int, title: str) -> None:
    """Append a section header with a blank line before it."""
    while lines and lines[-1] == "":
        lines.pop()
    if lines:
        lines.append("")
    lines.append(" " * indent + f"{title}:")


def emit_paragraphs(
    src: list[str], width: int, indent: int, list_indent: int | None = None, orphan_min: int = 1
) -> list[str]:
    """Wrap text while preserving lists, fenced code, tables, trees, and deeply-indented blocks."""
    out: list[str] = []
    buf: list[str] = []
    in_fence = False

    def flush():
        """Flush buffered paragraph with wrapping."""
        nonlocal buf
        if buf:
            out.extend(wrap_para(" ".join(x.strip() for x in buf), width, indent, min_words_per_line=orphan_min))
            buf = []

    for raw in src:
        s = raw.rstrip("\n")
        stripped = s.strip()
        if not stripped:
            flush()
            out.append("")
            continue
        if is_fence_line(s):
            flush()
            out.append(s.rstrip())
            in_fence = not in_fence
            continue
        if in_fence or is_table_like(s) or is_tree_like(s) or is_indented_block_line(s):
            flush()
            out.append(s.rstrip())
            continue
        if is_list_item(s):
            flush()
            out.append((" " * list_indent + stripped) if list_indent is not None else s.rstrip())
            continue
        buf.append(s)
    flush()
    while out and out[-1] == "":
        out.pop()
    return out


def parse_sections(text: str) -> dict[str, list[str]]:
    """Parse Google-style docstring into sections."""
    parts = {k: [] for k in ("summary", "description", *SECTIONS)}
    cur = "summary"
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if h := header_name(line):
            cur = h
            continue
        if not line.strip():
            if cur == "summary" and parts["summary"]:
                cur = "description"
            if parts[cur]:
                parts[cur].append("")
            continue
        parts[cur].append(line)
    return parts


def looks_like_param(s: str) -> bool:
    """Heuristic: True if line looks like a 'name: desc' param without being a list item."""
    if is_list_item(s) or ":" not in s:
        return False
    head = s.split(":", 1)[0].strip()
    return False if head in URLS else bool(head)


def iter_items(lines: list[str]) -> list[list[str]]:
    """Group lines into logical items separated by next param-like line."""
    items, i, n = [], 0, len(lines)
    while i < n:
        while i < n and not lines[i].strip():
            i += 1
        if i >= n:
            break
        item = [lines[i]]
        i += 1
        while i < n:
            st = lines[i].strip()
            if st and looks_like_param(st):
                break
            item.append(lines[i])
            i += 1
        items.append(item)
    return items


def format_structured_block(lines: list[str], width: int, base: int) -> list[str]:
    """Format Args/Returns/etc.; continuation at base+4, lists at base+8."""
    out: list[str] = []
    cont, lst = base + 4, base + 8
    for item in iter_items(lines):
        first = item[0].strip()
        name, desc = ([*first.split(":", 1), ""])[:2]
        name, desc = name.strip(), desc.strip()
        had_colon = ":" in first
        if not name or (" " in name and "(" not in name and ")" not in name):
            out.extend(emit_paragraphs(item, width, cont, lst, orphan_min=2))
            continue
        # Join continuation lines that aren't new paragraphs into desc
        parts = [desc] if desc else []
        tail, i = [], 1
        while i < len(item):
            line = item[i].strip()
            if not line or is_list_item(item[i]) or is_fence_line(item[i]) or is_table_like(item[i]):
                tail = item[i:]
                break
            parts.append(line)
            i += 1
        else:
            tail = []
        desc = " ".join(parts)
        head = " " * cont + (f"{name}: " if (desc or had_colon) else name)
        out.extend(wrap_hanging(head, desc, width, cont + 4))
        if tail:
            if body := emit_paragraphs(tail, width, cont + 4, lst, orphan_min=2):
                out.extend(body)
    return out


def detect_opener(original_literal: str) -> tuple[str, str, bool]:
    """Return (prefix, quotes, inline_hint) from the original string token safely."""
    s = original_literal.lstrip()
    i = 0
    while i < len(s) and s[i] in "rRuUbBfF":
        i += 1
    quotes = '"""'
    if i + 3 <= len(s) and s[i : i + 3] in ('"""', "'''"):
        quotes = s[i : i + 3]
    keep = "".join(ch for ch in s[:i] if ch in "rRuU")
    j = i + len(quotes)
    inline_hint = j < len(s) and s[j : j + 1] not in {"", "\n", "\r"}
    return keep, quotes, inline_hint


def format_google(text: str, indent: int, width: int, quotes: str, prefix: str, start_newline: bool) -> str:
    """Format multi-line Google-style docstring with start_newline controlling summary placement."""
    p = parse_sections(text)
    opener = prefix + quotes
    out: list[str] = []

    if p["summary"]:
        summary_text = " ".join(x.strip() for x in p["summary"]).strip()
        if summary_text and summary_text[-1] not in ".!?":
            summary_text += "."

        if start_newline:
            # Force newline: opener, blank line, then summary
            out.append(opener)
            # out.append("")
            out.extend(emit_paragraphs([summary_text], width, indent, list_indent=indent, orphan_min=1))
        else:
            # Force inline: summary on same line as opener
            eff_width = max(1, width - indent)
            out.extend(wrap_hanging(opener, summary_text, eff_width, indent))
    else:
        out.append(opener)

    if any(x.strip() for x in p["description"]):
        out.append("")
        out.extend(emit_paragraphs(p["description"], width, indent, list_indent=indent, orphan_min=1))

    has_content = bool(p["summary"]) or any(x.strip() for x in p["description"])
    for sec in ("Args", "Attributes", "Methods", "Returns", "Yields", "Raises"):
        if any(x.strip() for x in p[sec]):
            if has_content:
                add_header(out, indent, sec)
            else:
                out.append(" " * indent + f"{sec}:")
                has_content = True
            out.extend(format_structured_block(p[sec], width, indent))

    for sec in ("Examples", "Notes", "References"):
        if any(x.strip() for x in p[sec]):
            add_header(out, indent, sec)
            out.extend(x.rstrip() for x in p[sec])

    while out and out[-1] == "":
        out.pop()
    out.append(" " * indent + quotes)
    return "\n".join(out)


def likely_docstring_style(text: str) -> str:
    """Return 'google' | 'numpy' | 'rest' | 'epydoc' | 'unknown' for docstring text."""
    t = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if RST_FIELD_RX.search(t):
        return "rest"
    if EPYDOC_RX.search(t):
        return "epydoc"
    if NUMPY_UNDERLINE_SECTION_RX.search(t):
        return "numpy"
    return "google" if GOOGLE_SECTION_RX.search(t) else "unknown"


def format_docstring(
    content: str, indent: int, width: int, quotes: str, prefix: str, start_newline: bool = False
) -> str:
    """Single-line if short/sectionless/no-lists; else Google-style; preserve quotes/prefix."""
    if not content or not content.strip():
        return f"{prefix}{quotes}{quotes}"
    style = likely_docstring_style(content)
    if style in NON_GOOGLE:
        body = "\n".join(line.rstrip() for line in content.rstrip("\n").splitlines())
        return f"{prefix}{quotes}{body}{quotes}"
    text = content.strip()
    has_section = any(f"{s}:" in text for s in SECTIONS)
    has_list = any(is_list_item(line) for line in text.splitlines())
    single_ok = (
        ("\n" not in text)
        and not has_section
        and not has_list
        and (indent + len(prefix) + len(quotes) * 2 + len(text) <= width)
    )
    if single_ok:
        words = text.split()
        if words and not words[0].startswith(("http://", "https://")) and not words[0][0].isupper():
            words[0] = words[0][0].upper() + words[0][1:]
        out = " ".join(words)
        if out and out[-1] not in ".!?":
            out += "."
        return f"{prefix}{quotes}{out}{quotes}"
    return format_google(text, indent, width, quotes, prefix, start_newline)


class Visitor(ast.NodeVisitor):
    """Collect docstring replacements for classes and functions."""

    def __init__(self, src: list[str], width: int = 120, start_newline: bool = False):
        """Init with source lines, target width, and start_newline flag."""
        self.src, self.width, self.repl, self.start_newline = src, width, [], start_newline

    def visit_Module(self, node):
        """Skip module docstring; visit children."""
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Visit class definition and handle its docstring."""
        self._handle(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Visit function definition and handle its docstring."""
        self._handle(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Visit async function definition and handle its docstring."""
        self._handle(node)
        self.generic_visit(node)

    def _handle(self, node):
        """If first stmt is a string expr, schedule replacement."""
        try:
            doc = ast.get_docstring(node, clean=False)
            if not doc or not node.body or not isinstance(node.body[0], ast.Expr):
                return
            s = node.body[0].value
            if not (isinstance(s, ast.Constant) and isinstance(s.value, str)):
                return
            if likely_docstring_style(doc) in NON_GOOGLE:
                return
            sl, el = node.body[0].lineno - 1, node.body[0].end_lineno - 1
            sc, ec = node.body[0].col_offset, node.body[0].end_col_offset
            if sl < 0 or el >= len(self.src):
                return
            original = (
                self.src[sl][sc:ec]
                if sl == el
                else "\n".join([self.src[sl][sc:], *self.src[sl + 1 : el], self.src[el][:ec]])
            )
            prefix, quotes, _ = detect_opener(original)
            formatted = format_docstring(doc, sc, self.width, quotes, prefix, self.start_newline)
            if formatted.strip() != original.strip():
                self.repl.append((sl, el, sc, ec, formatted))
        except Exception:
            return


def format_python_file(text: str, width: int = 120, start_newline: bool = False) -> str:
    """Return source with reformatted docstrings; on failure, return original."""
    s = text
    if not s.strip():
        return s
    if ('"""' not in s and "'''" not in s) or ("def " not in s and "class " not in s and "async def " not in s):
        return s
    try:
        tree = ast.parse(s)
    except SyntaxError:
        return s
    src = s.splitlines()
    v = Visitor(src, width, start_newline=start_newline)
    try:
        v.visit(tree)
    except Exception:
        return s
    if not v.repl:
        return s
    for sl, el, sc, ec, rep in reversed(v.repl):
        try:
            if sl == el:
                src[sl] = src[sl][:sc] + rep + src[sl][ec:]
            else:
                nl = rep.splitlines()
                nl[0] = src[sl][:sc] + nl[0]
                nl[-1] += src[el][ec:]
                src[sl : el + 1] = nl
        except Exception:
            continue
    return "\n".join(src)


def preserve_trailing_newlines(original: str, formatted: str) -> str:
    """Preserve the original trailing newline count."""
    o = len(original) - len(original.rstrip("\n"))
    f = len(formatted) - len(formatted.rstrip("\n"))
    return formatted if o == f else formatted.rstrip("\n") + ("\n" * o)


def iter_py_files(paths: list[Path]) -> list[Path]:
    """Expand input paths to unique *.py files, pruning common env/build/cache dirs using pathlib."""
    out: list[Path] = []
    stack: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            stack.append(p)
    while stack:
        d = stack.pop()
        try:
            for child in d.iterdir():
                name = child.name
                if child.is_dir():
                    if name in EXCLUDED_DIR_NAMES or name.endswith(".egg-info") or child.is_symlink():
                        continue
                    stack.append(child)
                elif child.is_file() and child.suffix == ".py":
                    out.append(child)
        except Exception:
            continue
    return list(dict.fromkeys(sorted(out)))


def _process_file_worker(path: Path, width: int, check: bool, start_newline: bool) -> tuple[str, int, str]:
    """Worker: returns (path, status, msg). status: 0 unchanged, 1 changed, 2 error."""
    try:
        orig = path.read_text(encoding="utf-8")
        fmt = preserve_trailing_newlines(orig, format_python_file(orig, width, start_newline=start_newline))
        if check:
            return (str(path), 1 if orig != fmt else 0, "")
        if orig != fmt:
            path.write_text(fmt, encoding="utf-8")
            return (str(path), 1, "")
        return (str(path), 0, "")
    except Exception as e:
        return (str(path), 2, f"{e}")


def run(files: list[Path], width: int, check: bool, start_newline: bool, workers: int) -> tuple[int, int]:
    """Run processing serially or in parallel; returns (changed, errors)."""
    if workers <= 1 or len(files) <= 1:
        changed = errors = 0
        for f in files:
            p, status, msg = _process_file_worker(f, width, check, start_newline)
            if status == 1:
                print(f"  {p}")
                changed += 1
            elif status == 2:
                print(f"  ❌ {p}: {msg}")
                errors += 1
        return changed, errors
    changed = errors = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_process_file_worker, f, width, check, start_newline): f for f in files}
        for fut in as_completed(futs):
            p, status, msg = fut.result()
            if status == 1:
                print(f"  {p}")
                changed += 1
            elif status == 2:
                print(f"  ❌ {p}: {msg}")
                errors += 1
    return changed, errors


def parse_cli(argv: list[str]) -> tuple[list[Path], int, bool, bool]:
    """Parse command-line arguments.

    Processes CLI arguments to extract paths and formatting options. Supports '--check' for validation mode,
    '--start-newline' to force docstring summaries on new lines, and '--line-width=N' to set maximum line width.
    Non-flag arguments are treated as file or directory paths.

    Args:
        argv: List of command-line argument strings.

    Returns:
        paths: List of Path objects to process.
        width: Maximum line width for formatting (default 120).
        check: Bool for dry-run mode.
        start_newline: Bool controlling docstring summary placement.
    """
    width, check, paths, start_newline = 120, False, [], False
    for a in argv:
        if a == "--check":
            check = True
        elif a == "--start-newline":
            start_newline = True
        elif a.startswith("--line-width="):
            try:
                width = int(a.split("=", 1)[1])
            except ValueError:
                pass
        else:
            paths.append(Path(a))
    return paths, width, check, start_newline


def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]
    if not args:
        print("Usage: format_python_docstrings.py [--check] [--start-newline] [--line-width=120] <files_or_dirs...>")
        return
    paths, width, check, start_newline = parse_cli(args)
    files = iter_py_files(paths)
    if not files:
        print("⚠️ No Python files found")
        return
    workers = min(8, len(files), os.cpu_count() or 1)
    root = paths[0].resolve() if paths else Path.cwd().resolve()
    t0 = time.time()
    action = "🔍 Checking" if check else "🔧 Formatting"
    print(
        f"{action} {len(files)} file{'s' if len(files) != 1 else ''} in {root} with {workers} worker{'s' if workers != 1 else ''}"
    )
    changed, nerr = run(files, width, check, start_newline, workers)
    dur = time.time() - t0
    if changed:
        verb = "would be reformatted" if check else "reformatted"
        unchanged = len(files) - changed - nerr
        parts = [f"{changed} file{'s' if changed != 1 else ''} {verb}"]
        if unchanged > 0:
            parts.append(f"{unchanged} file{'s' if unchanged != 1 else ''} left unchanged")
        if nerr:
            parts.append(f"{nerr} error{'s' if nerr != 1 else ''}")
        print(f"✅ {', '.join(parts)} ({dur:.1f}s)")
        if check:
            sys.exit(1)
    else:
        msg = f"{len(files) - nerr} file{'s' if (len(files) - nerr) != 1 else ''} left unchanged"
        if nerr:
            msg += f", {nerr} error{'s' if nerr != 1 else ''}"
        print(f"✅ {msg} ({dur:.1f}s)")


if __name__ == "__main__":
    main()
