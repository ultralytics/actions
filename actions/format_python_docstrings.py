# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import ast
import re
import sys
import time
from pathlib import Path


SECTIONS = ("Args", "Attributes", "Methods", "Returns", "Yields", "Raises", "Example", "Notes", "References")
LIST_RX = re.compile(r"""^(\s*)(?:[-*•]\s+|(?:\d+|[A-Za-z]+)[\.\)]\s+)""")


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

    # Rebalance to avoid too-short continuation lines when requested
    if min_words_per_line > 1:
        i = 1
        while i < len(lines):
            if len(lines[i]) < min_words_per_line and len(lines[i - 1]) > 1:
                donor = lines[i - 1][-1]
                this_len = len(pad) + sum(len(w) for w in lines[i]) + (len(lines[i]) - 1)
                if this_len + (1 if lines[i] else 0) + len(donor) <= width:
                    lines[i - 1].pop()
                    lines[i].insert(0, donor)
                    if i - 1 > 0 and len(lines[i - 1]) == 1:
                        i -= 1
                        continue
            i += 1

    return [pad + " ".join(line) for line in lines]


def wrap_para(text: str, width: int, indent: int, min_words_per_line: int = 1) -> list[str]:
    """Wrap a paragraph string; orphan control via min_words_per_line."""
    text = text.strip()
    if not text:
        return []
    return wrap_words(text.split(), width, indent, min_words_per_line)


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
            take.append(w); used += need
        else:
            break

    out: list[str] = []
    if take:
        out.append(head + " ".join(take))
        rest = words[len(take):]
    else:
        out.append(head.rstrip())
        rest = words

    out.extend(wrap_words(rest, width, cont_indent, min_words_per_line=2))
    return out


def is_list_item(s: str) -> bool:
    """True if s looks like a bullet/numbered list item."""
    return bool(LIST_RX.match(s.lstrip()))


def header_name(line: str) -> str | None:
    """Return canonical section header or None."""
    s = line.strip()
    if not s.endswith(":") or len(s) <= 1:
        return None
    name = s[:-1].strip()
    if name == "Examples":
        name = "Example"
    if name == "Note":
        name = "Notes"
    return name if name in SECTIONS else None


def add_header(lines: list[str], indent: int, title: str, opener_line: str) -> None:
    """Append a section header; no blank before first header, exactly one before subsequent ones."""
    while lines and lines[-1] == "":
        lines.pop()
    if lines and lines[-1] != opener_line:
        lines.append("")
    lines.append(" " * indent + f"{title}:")


def emit_paragraphs(
    src: list[str], width: int, indent: int, list_indent: int | None = None, orphan_min: int = 1
) -> list[str]:
    """Emit paragraphs from src: wrap normal text, preserve list items; keep internal blank lines.

    orphan_min controls the minimum words per continuation line; use 1 for plain paragraphs,
    and 2 for Args/Returns continuation bodies to avoid orphans like a single word line.
    """
    out: list[str] = []
    buf: list[str] = []

    def flush():
        nonlocal buf
        if buf:
            out.extend(wrap_para(" ".join(x.strip() for x in buf), width, indent, min_words_per_line=orphan_min))
            buf = []

    for raw in src:
        s = raw.rstrip()
        if not s.strip():
            flush()
            out.append("")
        elif is_list_item(s):
            flush()
            out.append((" " * list_indent + s.strip()) if list_indent is not None else s)
        else:
            buf.append(s)
    flush()
    while out and out[-1] == "":
        out.pop()
    return out


def parse_sections(text: str) -> dict[str, list[str]]:
    """Parse Google-style docstring into sections."""
    parts = {k: [] for k in ("summary", "description") + SECTIONS}
    cur = "summary"
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        h = header_name(line)
        if h:
            cur = h; continue
        if not line.strip():
            if cur == "summary" and parts["summary"]:
                cur = "description"
            if parts[cur]:
                parts[cur].append("")
            continue
        parts[cur].append(line)
    return parts


def looks_like_param(s: str) -> bool:
    """Heuristic: 'name:' without being a list item."""
    if is_list_item(s) or ":" not in s:
        return False
    head = s.split(":", 1)[0].strip()
    return bool(head)


def iter_items(lines: list[str]) -> list[list[str]]:
    """Group lines into logical items separated by next param."""
    items, i, n = [], 0, len(lines)
    while i < n:
        while i < n and not lines[i].strip():
            i += 1
        if i >= n:
            break
        item = [lines[i]]; i += 1
        while i < n:
            st = lines[i].strip()
            if st and looks_like_param(st):
                break
            item.append(lines[i]); i += 1
        items.append(item)
    return items


def format_structured_block(lines: list[str], width: int, base: int) -> list[str]:
    """Format Args/Returns/etc.; continuation at base+4, lists at base+8."""
    out: list[str] = []
    cont, lst = base + 4, base + 8
    for item in iter_items(lines):
        first = item[0].strip()
        name, desc = (first.split(":", 1) + [""])[:2]
        name, desc = name.strip(), desc.strip()

        # Free text item (not 'name: desc')
        if not name or (" " in name and "(" not in name and ")" not in name):
            out.extend(emit_paragraphs(item, width, cont, lst, orphan_min=2))
            continue

        head = " " * cont + f"{name}: "
        out.extend(wrap_hanging(head, desc, width, cont + 4))

        # Continuation (paragraphs + lists) with orphan control
        tail = item[1:]
        if tail:
            body = emit_paragraphs(tail, width, cont + 4, lst, orphan_min=2)
            if body:
                out.extend(body)
    return out


def detect_opener(original_literal: str) -> tuple[str, str]:
    """Return (prefix, quotes) from the original string token safely."""
    s = original_literal.lstrip()
    i = 0
    while i < len(s) and s[i] in "rRuUbBfF":
        i += 1
    quotes = '"""'
    if i + 3 <= len(s) and s[i:i + 3] in ('"""', "'''"):
        quotes = s[i:i + 3]
    keep = "".join(ch for ch in s[:i] if ch in "rRuU")  # preserve only r/R/u/U
    return keep, quotes


def format_google(text: str, indent: int, width: int, quotes: str, prefix: str) -> str:
    """Format multi-line Google-style docstring with given quotes/prefix."""
    p = parse_sections(text)
    opener = prefix + quotes
    out = [opener]
    if p["summary"]:
        out.extend(emit_paragraphs(p["summary"], width, indent, orphan_min=1))
    if any(x.strip() for x in p["description"]):
        out.append("")
        out.extend(emit_paragraphs(p["description"], width, indent, orphan_min=1))
    for sec in ("Args", "Attributes", "Methods", "Returns", "Yields", "Raises"):
        if any(x.strip() for x in p[sec]):
            add_header(out, indent, sec, opener)
            out.extend(format_structured_block(p[sec], width, indent))
    for sec in ("Example", "Notes", "References"):
        if any(x.strip() for x in p[sec]):
            title = "Examples" if sec == "Example" else sec
            add_header(out, indent, title, opener)
            out.extend(x.rstrip() for x in p[sec])
    while out and out[-1] == "":
        out.pop()
    out.append(" " * indent + quotes)
    return "\n".join(out)


def format_docstring(content: str, indent: int, width: int, quotes: str, prefix: str) -> str:
    """Single-line if short/sectionless/no-lists; else Google-style. Preserve quotes/prefix."""
    if not content or not content.strip():
        return f"{prefix}{quotes}{quotes}"
    text = content.strip()
    has_section = any(f"{s}:" in text for s in SECTIONS + ("Examples",))
    has_list = any(is_list_item(l) for l in text.splitlines())
    single_ok = ("\n" not in text) and not has_section and not has_list and (
        indent + len(prefix) + len(quotes) * 2 + len(text) <= width
    )
    if single_ok:
        words = text.split()
        if words and not (words[0].startswith(("http://", "https://")) or words[0][0].isupper()):
            words[0] = words[0][0].upper() + words[0][1:]
        out = " ".join(words)
        if out and out[-1] not in ".!?":
            out += "."
        return f"{prefix}{quotes}{out}{quotes}"
    return format_google(text, indent, width, quotes, prefix)


class Visitor(ast.NodeVisitor):
    """Collect docstring replacements for classes and functions."""

    def __init__(self, src: list[str], width: int = 120):
        """Init with source lines and target width."""
        self.src, self.width, self.repl = src, width, []

    def visit_Module(self, node):  # noqa: N802
        """Skip module docstring; visit children."""
        self.generic_visit(node)

    def visit_ClassDef(self, node):  # noqa: N802
        self._handle(node); self.generic_visit(node)

    def visit_FunctionDef(self, node):  # noqa: N802
        self._handle(node); self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):  # noqa: N802
        self._handle(node); self.generic_visit(node)

    def _handle(self, node):
        """If first stmt is a string expr, schedule replacement."""
        try:
            doc = ast.get_docstring(node, clean=False)
            if not doc or not node.body or not isinstance(node.body[0], ast.Expr):
                return
            s = node.body[0].value
            if not (isinstance(s, ast.Constant) and isinstance(s.value, str)):
                return
            sl, el = node.body[0].lineno - 1, node.body[0].end_lineno - 1
            sc, ec = node.body[0].col_offset, node.body[0].end_col_offset
            if sl < 0 or el >= len(self.src):
                return
            original = (
                self.src[sl][sc:ec]
                if sl == el
                else "\n".join([self.src[sl][sc:]] + self.src[sl + 1 : el] + [self.src[el][:ec]])
            )
            prefix, quotes = detect_opener(original)
            formatted = format_docstring(doc, sc, self.width, quotes, prefix)
            if formatted.strip() != original.strip():
                self.repl.append((sl, el, sc, ec, formatted))
        except Exception:
            return


def format_python_file(text: str, width: int = 120) -> str:
    """Return source with reformatted docstrings; on failure, return original."""
    if not text.strip():
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    src = text.splitlines()
    v = Visitor(src, width)
    try:
        v.visit(tree)
    except Exception:
        return text
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
    """Expand input paths to sorted unique *.py files."""
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(p.rglob("*.py")))
        elif p.is_file() and p.suffix == ".py":
            out.append(p)
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f); uniq.append(f)
    return uniq


def process_file(path: Path, width: int = 120, check: bool = False) -> bool:
    """Process one file; True if unchanged/success, False if changed."""
    if path.suffix != ".py":
        return True
    try:
        orig = path.read_text(encoding="utf-8")
        fmt = preserve_trailing_newlines(orig, format_python_file(orig, width))
        if check:
            if orig != fmt:
                print(f"  {path}"); return False
            return True
        if orig != fmt:
            path.write_text(fmt, encoding="utf-8")
            print(f"  {path}"); return False
        return True
    except Exception as e:
        print(f"  Error: {path}: {e}")
        return True


def parse_cli(argv: list[str]) -> tuple[list[Path], int, bool]:
    """Minimal argv parser: (paths, width, check)."""
    width, check, paths = 120, False, []
    for a in argv:
        if a == "--check":
            check = True
        elif a.startswith("--line-width="):
            try:
                width = int(a.split("=", 1)[1])
            except ValueError:
                pass
        else:
            paths.append(Path(a))
    return paths, width, check


def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]
    if not args:
        print("Usage: format_python_docstrings.py [--check] [--line-width=120] <files_or_dirs...>")
        return
    paths, width, check = parse_cli(args)
    files = iter_py_files(paths)
    if not files:
        print("No Python files found"); return

    t0 = time.time()
    print(f"{'Checking' if check else 'Formatting'} {len(files)} file{'s' if len(files) != 1 else ''}")
    changed = sum(not process_file(f, width, check) for f in files)

    dur = time.time() - t0
    if changed:
        verb = "would be reformatted" if check else "reformatted"
        unchanged = len(files) - changed
        parts = []
        if changed: parts.append(f"{changed} file{'s' if changed != 1 else ''} {verb}")
        if unchanged: parts.append(f"{unchanged} file{'s' if unchanged != 1 else ''} left unchanged")
        print(f"{', '.join(parts)} ({dur:.1f}s)")
        if check:
            sys.exit(1)
    else:
        print(f"{len(files)} file{'s' if len(files) != 1 else ''} left unchanged ({dur:.1f}s)")


if __name__ == "__main__":
    main()
