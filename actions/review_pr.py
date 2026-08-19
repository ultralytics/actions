# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import quote

from .utils import (
    ACTIONS_CREDIT,
    COMMON_EXCLUDED_DIRS,
    DIFF_FILE_PATTERN,
    GITHUB_API_URL,
    MAX_PROMPT_CHARS,
    Action,
    format_skipped_files_dropdown,
    get_agent_response,
    get_review_model,
    remove_html_comments,
    sanitize_ai_text,
    should_skip_file,
)
from .utils.openai_utils import _is_anthropic_model

REVIEW_MARKER = "## 🔍 PR Review"
ERROR_MARKER = "⚠️ Review generation encountered an error"
EMOJI_MAP = {"CRITICAL": "❗", "HIGH": "⚠️", "MEDIUM": "💡", "LOW": "📝", "SUGGESTION": "💭"}
MAX_CONTEXT_FILE_CHARS = 12000
MAX_REVIEW_COMMENTS = 8
MAX_TOOL_OUTPUT_CHARS = 40000
MAX_TOOL_FILE_LINES = 400
MAX_AGENT_TURNS = 24
REVIEW_PROMPT_CHARS = round(MAX_PROMPT_CHARS * 1.5)  # reviews favor evidence depth over one-shot cost
MAX_HISTORY_REVIEWS = 5  # prior reviews included in the prompt (the full history stays available via the tool)
MAX_HISTORY_ITEM_CHARS = 8000  # per prior review or response, enough for a full summary plus its findings log
MAX_HISTORY_CHARS = 20000
MAX_FINDING_LOG_CHARS = 500  # per finding logged in the review body, the record that outlives its inline comment
REVIEW_COST_SOFT_LIMIT = 5.00  # quality-first budget; stop requesting tools after this soft limit
MAX_APPROVED_FILE_SIZE = 1_000_000
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SUGGESTION": 4, None: 5}


def _clip_tool_output(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Limit model-facing tool output size."""
    return text if len(text) <= limit else f"{text[:limit].rstrip()}\n... (truncated)"


def _iter_repo_files(path_glob=None):
    """Yield repository files, including hidden files, pruning vendored dirs and paths outside the checkout."""
    root = Path.cwd().resolve()
    stack = [root]
    while stack:
        try:
            children = list(stack.pop().iterdir())
        except OSError:
            continue
        for path in children:
            if path.is_dir():
                if path.name not in COMMON_EXCLUDED_DIRS and not path.is_symlink():
                    stack.append(path)
                continue
            rel = path.relative_to(root).as_posix()
            if (path_glob and not fnmatch(rel, path_glob)) or should_skip_file(rel):
                continue
            try:
                target = path.resolve()
                target.relative_to(root)
            except (OSError, ValueError):
                continue
            if target.is_file():
                yield target, rel


def search_repo(query: str, path_glob=None) -> str:
    """Search repository text for agent review context."""
    if not query:
        return "query is required."
    matches = []
    for target, rel in _iter_repo_files(path_glob):
        if target.stat().st_size > 500_000:
            continue
        for line_no, line in enumerate(target.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if query in line:
                matches.append(f"{rel}:{line_no}:{line}")
                if len(matches) >= 200:
                    return _clip_tool_output("\n".join(matches))
    return _clip_tool_output("\n".join(matches)) if matches else "No matches found."


def _clip(text: str, limit: int | None) -> str:
    """Clip text to at most limit characters, or return it unchanged when no limit is given."""
    return text if not limit or len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


def _oversized_files(
    paths: list[str], event: Action, head_sha: str, local_checkout: bool
) -> tuple[list[str], list[str]]:
    """Return changed files over the approval limit and files whose size could not be verified."""
    root = Path.cwd().resolve()
    oversized, unverified = [], []
    for path in sorted(set(paths)):
        if local_checkout:
            target = (root / path).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                unverified.append(path)
                continue
            if not target.exists():  # deleted file
                continue
            try:
                size = target.stat().st_size
            except OSError:
                unverified.append(path)
                continue
        else:
            url = f"{GITHUB_API_URL}/repos/{event.repository}/contents/{quote(path, safe='/')}?ref={head_sha}"
            response = event.get(url)
            if response.status_code == 404:  # deleted file
                continue
            if response.status_code != 200 or not isinstance((size := response.json().get("size")), int):
                unverified.append(path)
                continue
        if size > MAX_APPROVED_FILE_SIZE:
            oversized.append(path)
    return oversized, unverified


def _build_review_history(reviews: list[dict], comments: list[dict], bot_username: str | None) -> dict:
    """Capture prior bot reviews and the responses to them; each review body carries its own findings log."""
    parents = {comment.get("id"): comment for comment in comments}
    owned_ids = {review.get("id") for review in reviews}
    prior = []
    for number, review in enumerate(reviews, 1):
        body = re.sub(rf"{re.escape(REVIEW_MARKER)} *\d*", "", review.get("body") or "").replace(ACTIONS_CREDIT, "")
        prior.append(
            {
                "number": number,
                "commit": (review.get("commit_id") or "")[:7],
                "body": body.split("<details><summary>📋 Skipped")[0].strip(),
            }
        )

    replies, others = [], []
    for comment in comments:
        if (login := comment.get("user", {}).get("login")) == bot_username:
            continue
        parent = parents.get(comment.get("in_reply_to_id")) or {}
        line = comment.get("line") or comment.get("original_line") or 0
        entry = f"- {comment.get('path')}:{line} @{login} ({comment.get('author_association') or 'NONE'})"
        body = (comment.get("body") or "").strip()
        if parent.get("pull_request_review_id") in owned_ids:  # a reply to one of our own findings
            replies.append(f'{entry} on "{_clip((parent.get("body") or "").strip(), 120)}": {body}')
        else:
            others.append(f"{entry}: {body}")
    return {"reviews": prior, "replies": replies, "others": others}


def _fit(entries: list[str], budget: int | None, separator: int = 1) -> tuple[list[str], int]:
    """Keep the newest entries that fit the budget, oldest first, with the count of those dropped."""
    kept, used = [], 0
    for entry in reversed(entries):
        cost = len(entry) + (separator if kept else 0)  # separators only sit between entries
        if budget and used + cost > budget:
            break
        kept.append(entry)
        used += cost
    return kept[::-1], len(entries) - len(kept)


def _format_review_history(
    history: dict, limit: int | None = None, clip: int | None = None, budget: int | None = None
) -> str:
    """Render prior reviews and the responses to them as review context, oldest dropped first when over budget."""
    sections = []
    share = budget // 4 if budget else None  # each response section gets a quarter, leaving half for the reviews
    for title, key in (("Other review comments on this PR", "others"), ("Replies to your findings", "replies")):
        if entries := history.get(key):
            kept, dropped = _fit([_clip(e, share or clip) for e in entries], share)  # clipped to fit, never dropped
            note = f" ({dropped} older comment(s) omitted for length)" if dropped else ""
            sections.append(f"### {title}{note}\n" + "\n".join(kept))

    reviews = history.get("reviews") or []
    shown = reviews[-limit:] if limit else reviews
    rendered = [f"### Review {r['number']} (commit {r['commit']})\n{_clip(r['body'], clip)}" for r in shown]
    remaining = budget - sum(len(s) + 2 for s in sections) if budget else None
    kept, dropped = _fit(rendered, remaining, separator=2)
    if omitted := dropped + len(reviews) - len(shown):
        kept.insert(0, f"### {omitted} older review(s) omitted for length")
    return "\n\n".join(kept + sections)


def _fetch_head_file(event: Action, sha: str, path: str) -> str | None:
    """Fetch one file's text from the PR head via the GitHub contents API; None only if it does not exist (404)."""
    url = f"{GITHUB_API_URL}/repos/{event.repository}/contents/{quote(path)}?ref={sha}"
    headers = {**event.headers, "Accept": "application/vnd.github.raw+json"}
    response = event.get(url, headers=headers, expected_status=[200, 404])
    if response.status_code == 200:
        return response.text
    if response.status_code == 404:
        return None
    raise RuntimeError(f"fetch failed for {path} at PR head: HTTP {response.status_code}")


def _read_head_file(event: Action, head_sha: str | None, local_checkout: bool, path: str) -> str | None:
    """Read one file's text from the PR head: verified local checkout first (no API calls), GitHub API fallback."""
    if local_checkout:
        root = Path.cwd().resolve()
        target = (root / path).resolve()
        target.relative_to(root)  # raises ValueError for paths or symlinks escaping the checkout
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8", errors="ignore")
    if not (event and head_sha):
        return None
    return _fetch_head_file(event, head_sha, path)


def _split_augmented_diff_by_file(augmented_diff: str) -> dict[str, list[str]]:
    """Split an augmented diff into per-file chunks."""
    chunks, current_file = {}, None
    for line in augmented_diff.splitlines():
        if line.startswith("diff --git"):
            match = DIFF_FILE_PATTERN.search(line)
            current_file = match.group(1).rstrip('"') if match else None
            if current_file:
                chunks[current_file] = []
        if current_file:
            chunks[current_file].append(line)
    return chunks


def build_review_agent_tools(
    diff_files: dict | None = None,
    augmented_diff: str = "",
    event: Action = None,
    head_sha: str | None = None,
    local_checkout: bool = False,
    review_history: dict | None = None,
) -> tuple[list[dict], dict]:
    """Build read-only tools for the PR review agent, reading files from the PR head via the GitHub API."""
    diff_files = diff_files or {}
    review_history = review_history or {}
    diff_chunks = _split_augmented_diff_by_file(augmented_diff)
    head_tree = []  # cached PR head file listing
    discussion = []  # cached PR discussion comments

    def read_file(path: str, start_line=None, end_line=None) -> str:
        """Read a bounded line range from a file at the PR head."""
        if should_skip_file(path):
            return f"{path} is skipped because it is generated, vendored, or too large."
        try:
            text = _read_head_file(event, head_sha, local_checkout, path)
        except ValueError:
            return f"path must stay inside repository: {path}"
        if text is None:
            return f"{path} does not exist at the PR head."
        if len(text) > 500_000:
            return f"{path} is skipped because it is generated, vendored, or too large."
        lines = text.splitlines()
        start = max(1, int(start_line or 1))
        end = min(len(lines), int(end_line or len(lines)), start + MAX_TOOL_FILE_LINES - 1)
        if end < start:
            return f"{path} has no lines in requested range {start}-{end}."
        numbered = "\n".join(f"{i:>5}: {lines[i - 1]}" for i in range(start, end + 1))
        return _clip_tool_output(f"{path}:{start}-{end}\n{numbered}")

    def list_files(path_glob=None) -> str:
        """List files at the PR head matching an optional glob."""
        if local_checkout:
            files = sorted(rel for _, rel in _iter_repo_files(path_glob))
            return _clip_tool_output("\n".join(files[:300])) if files else "No matching files found."
        if not (event and head_sha):
            return "list_files is unavailable: no PR head to list from."
        if not head_tree:
            response = event.get(f"{GITHUB_API_URL}/repos/{event.repository}/git/trees/{head_sha}?recursive=1")
            if response.status_code != 200:
                raise RuntimeError(f"list_files failed: HTTP {response.status_code}")
            head_tree.append([t["path"] for t in response.json().get("tree", []) if t.get("type") == "blob"])
        files = sorted(p for p in head_tree[0] if (not path_glob or fnmatch(p, path_glob)) and not should_skip_file(p))
        return _clip_tool_output("\n".join(files[:300])) if files else "No matching files found."

    def list_changed_files(path_glob=None) -> str:
        """List changed files in this PR with added/removed line counts."""
        rows = []
        for path in sorted(diff_files):
            if path_glob and not fnmatch(path, path_glob):
                continue
            sides = diff_files[path]
            rows.append(f"{path} (+{len(sides['RIGHT'])}/-{len(sides['LEFT'])})")
        return _clip_tool_output("\n".join(rows)) if rows else "No changed files found."

    def read_diff(path: str, start_line=None, end_line=None) -> str:
        """Read the line-numbered augmented diff for one changed file."""
        if path not in diff_chunks:
            return f"{path} is not in the changed-file diff."
        lines = diff_chunks[path]
        start = max(1, int(start_line or 1))
        end = min(len(lines), int(end_line or len(lines)))
        if end < start:
            return f"{path} has no diff lines in requested range {start}-{end}."
        return _clip_tool_output(f"{path} diff:{start}-{end}\n" + "\n".join(lines[start - 1 : end]))

    def read_pr_conversation() -> str:
        """Read every prior review of this PR in full, plus the discussion on it."""
        parts = [_format_review_history(review_history, budget=MAX_TOOL_OUTPUT_CHARS)]
        if event and (pr_number := (event.pr or {}).get("number")) and not discussion:
            url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{pr_number}/comments"
            discussion.append(
                [
                    f"@{c.get('user', {}).get('login')}: {_clip((c.get('body') or '').strip(), 1000)}"
                    for c in event.paginate(url, hard=True)
                ]
            )
        if discussion and discussion[0]:
            parts.append("### PR discussion comments\n" + "\n".join(discussion[0]))
        return _clip_tool_output("\n\n".join(parts))

    tools = [
        {"type": "web_search"},
        {
            "type": "function",
            "name": "list_changed_files",
            "description": (
                "List every changed file in the PR with added/removed line counts. Use this when the PR has many "
                "files or the initial diff is truncated so every changed file can be considered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path_glob": {"type": ["string", "null"], "description": "Optional changed-file glob, or null."},
                },
                "required": ["path_glob"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "read_diff",
            "description": (
                "Read the line-numbered augmented diff for one changed file. Use this to inspect changed hunks that "
                "were not included in the initial prompt or to recover exact R/L line numbers for inline comments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Changed file path from list_changed_files."},
                    "start_line": {"type": ["integer", "null"], "description": "1-based diff output line, or null."},
                    "end_line": {"type": ["integer", "null"], "description": "1-based diff output line, or null."},
                },
                "required": ["path", "start_line", "end_line"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "read_pr_conversation",
            "description": (
                "Read every earlier review of this PR in full - their summaries, inline findings, and the replies "
                "to them - plus the PR discussion comments. Use this before repeating, contradicting, or "
                "reversing an earlier finding, and whenever the PRIOR REVIEWS excerpt in the prompt is truncated."
            ),
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            "strict": True,
        },
        {
            "type": "function",
            "name": "read_file",
            "description": (
                "Read a bounded line range from a repository file at the PR head, including unchanged files such as "
                "pyproject.toml, tests, configs, and shared helpers. Use this to verify changed code or nearby "
                "definitions before making a review finding."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository-relative file path."},
                    "start_line": {"type": ["integer", "null"], "description": "1-based first line, or null."},
                    "end_line": {"type": ["integer", "null"], "description": "1-based last line, or null."},
                },
                "required": ["path", "start_line", "end_line"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "search_repo",
            "description": (
                "Search the checked-out repository. Use focused literal strings to find related "
                "definitions, dependencies, tests, config, or prior patterns before deciding whether a diff hunk is "
                "wrong."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Literal string to search for."},
                    "path_glob": {"type": ["string", "null"], "description": "Optional glob, or null."},
                },
                "required": ["query", "path_glob"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "list_files",
            "description": "List repository files matching an optional glob when you need to locate related files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path_glob": {"type": ["string", "null"], "description": "Optional glob, or null."},
                },
                "required": ["path_glob"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ]
    handlers = {
        "list_changed_files": list_changed_files,
        "read_diff": read_diff,
        "read_file": read_file,
        "read_pr_conversation": read_pr_conversation,
        "search_repo": search_repo,
        "list_files": list_files,
    }
    if not local_checkout:  # repo text search needs a checkout of the PR head; drop it instead of returning empty
        tools = [t for t in tools if t.get("name") != "search_repo"]
        del handlers["search_repo"]
    if not review_history.get("reviews"):  # nothing to read back on a first review
        tools = [t for t in tools if t.get("name") != "read_pr_conversation"]
        del handlers["read_pr_conversation"]
    return tools, handlers


def get_repo_guidelines(
    model: str = "", event: Action = None, head_sha: str | None = None, local_checkout: bool = False
) -> str:
    """Read repository guidelines (one agent file + CONTRIBUTING.md) from the PR head."""
    guidelines = []
    # Prefer CLAUDE.md for Anthropic models, AGENTS.md for others; load only one, never both
    agent_prefs = ("CLAUDE.md", "AGENTS.md") if "claude" in model.lower() else ("AGENTS.md", "CLAUDE.md")
    for filename in ("CONTRIBUTING.md", *agent_prefs):
        content = (_read_head_file(event, head_sha, local_checkout, filename) or "")[:MAX_CONTEXT_FILE_CHARS]
        if content:
            guidelines.append(f"### {filename}\n~~~\n{content}\n~~~")
            print(f"Loaded {filename} ({len(content)} chars) for review context")
            if filename in agent_prefs:
                break  # Only load one agent guidelines file
    return f"PROJECT GUIDELINES:\n{chr(10).join(guidelines)}\n\n" if guidelines else ""


def parse_diff_files(diff_text: str) -> tuple[dict, str]:
    """Parse diff and return file mapping with line numbers AND augmented diff with explicit line numbers.

    Structure: files[file]["RIGHT"][line] -> str (added line text) files[file]["LEFT"][line] -> str (removed line text)
    files[file]["_HUNK"]["RIGHT"][line] -> int (hunk id) files[file]["_HUNK"]["LEFT"][line] -> int (hunk id)
    """
    files, current_file, new_line, old_line = {}, None, 0, 0
    augmented_lines, hunk_id = [], -1

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            match = DIFF_FILE_PATTERN.search(line)
            current_file = match.group(1).rstrip('"') if match else None
            new_line, old_line, hunk_id = 0, 0, -1
            if current_file:
                files[current_file] = {"RIGHT": {}, "LEFT": {}, "_HUNK": {"RIGHT": {}, "LEFT": {}}}
            augmented_lines.append(line)
        elif line.startswith("@@") and current_file:
            if match := re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?", line):
                old_line, new_line = int(match.group(1)), int(match.group(2))
                hunk_id += 1
            augmented_lines.append(line)
        elif current_file and (new_line > 0 or old_line > 0):
            if line.startswith("+") and not line.startswith("+++"):
                files[current_file]["RIGHT"][new_line] = line[1:]
                files[current_file]["_HUNK"]["RIGHT"][new_line] = hunk_id
                augmented_lines.append(f"R{new_line:>5} {line}")  # Prefix with RIGHT line number
                new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                files[current_file]["LEFT"][old_line] = line[1:]
                files[current_file]["_HUNK"]["LEFT"][old_line] = hunk_id
                augmented_lines.append(f"L{old_line:>5} {line}")  # Prefix with LEFT line number
                old_line += 1
            elif not line.startswith("\\"):
                augmented_lines.append(f"       {line}")  # Context line, no number
                new_line += 1
                old_line += 1
            else:
                augmented_lines.append(line)
        else:
            augmented_lines.append(line)

    files = {path: sides for path, sides in files.items() if sides["RIGHT"] or sides["LEFT"]}
    return files, "\n".join(augmented_lines)


def generate_pr_review(
    repository: str,
    diff: tuple[str, list[str]],
    pr_title: str,
    pr_description: str,
    event: Action = None,
    head_sha: str | None = None,
    review_history: dict | None = None,
) -> dict:
    """Generate comprehensive PR review with line-specific comments and overall assessment."""
    diff_text, skipped_files = diff
    review_history = review_history or {}
    prior_reviews = review_history.get("reviews") or []
    head_sha = head_sha or (event.get_pr_head_sha() if event else None)
    if diff_text.startswith("ERROR:"):
        return {"comments": [], "summary": f"{ERROR_MARKER}: {diff_text}", "head_sha": head_sha}
    diff_files, augmented_diff = parse_diff_files(diff_text) if diff_text else ({}, "")
    file_list = list(diff_files.keys())
    local_checkout = _verified_local_checkout(head_sha)
    if head_sha:
        print(f"Reviewing PR head {head_sha[:7]} ({'local checkout' if local_checkout else 'via GitHub API'})")
    oversized_files, unverified_sizes = _oversized_files(file_list + skipped_files, event, head_sha, local_checkout)
    if oversized_files or unverified_sizes:
        details = []
        if oversized_files:
            details.append(f"Files larger than 1 MB: {', '.join(f'`{path}`' for path in oversized_files)}")
        if unverified_sizes:
            details.append(f"File sizes could not be verified: {', '.join(f'`{path}`' for path in unverified_sizes)}")
        return {
            "comments": [],
            "summary": "Cannot approve this PR. " + " ".join(details),
            "diff_files": diff_files,
            "oversized_files": oversized_files,
            "unverified_sizes": unverified_sizes,
            "skipped_files": skipped_files,
            "head_sha": head_sha,
        }
    if not diff_files:
        summary = (
            f"All {len(skipped_files)} changed files are generated/vendored (skipped review)"
            if skipped_files
            else "No changes detected in diff"
        )
        return {"comments": [], "summary": summary, "skipped_files": skipped_files, "head_sha": head_sha}

    lines_changed = sum(len(sides["RIGHT"]) + len(sides["LEFT"]) for sides in diff_files.values())

    # Read model-appropriate guidelines from the PR head for project-specific review context
    review_model = get_review_model()
    is_agent_review_model = not _is_anthropic_model(review_model)
    guidelines_section = get_repo_guidelines(review_model, event, head_sha, local_checkout)

    # Carry prior reviews of this PR forward so findings are not repeated, contradicted, or silently reversed
    history_section = ""
    if prior_reviews:
        excerpt = _format_review_history(
            review_history, limit=MAX_HISTORY_REVIEWS, clip=MAX_HISTORY_ITEM_CHARS, budget=MAX_HISTORY_CHARS
        )
        history_section = f"PRIOR REVIEWS OF THIS PR (oldest first):\n{excerpt}\n\n"
        print(f"Loaded {len(prior_reviews)} prior review(s) ({len(history_section)} chars) for review context")

    # Fetch full file contents for better context if within token budget
    full_files_section = ""
    if event and head_sha and not is_agent_review_model and len(file_list) <= 10:  # Reasonable file count limit
        file_contents, total_chars = [], len(augmented_diff) + len(guidelines_section) + len(history_section)
        for file_path in file_list:
            text = _read_head_file(event, head_sha, local_checkout, file_path) or ""
            if not text or len(text) > 100_000:  # skip missing and >100KB files entirely
                continue
            snippet = text[:MAX_CONTEXT_FILE_CHARS]
            if len(snippet) == MAX_CONTEXT_FILE_CHARS:
                snippet = f"{snippet.rstrip()}\n... (truncated)"
            # Only include if within budget, include buffer for Markdown noise
            estimated_cost = len(snippet) + 200
            if total_chars + estimated_cost >= REVIEW_PROMPT_CHARS:
                break  # Stop when we hit budget limit
            file_contents.append(f"### {file_path}\n```\n{snippet}\n```")
            total_chars += estimated_cost
        if file_contents:
            full_files_section = f"FULL FILE CONTENTS:\n{chr(10).join(file_contents)}\n\n"

    # Remaining budget for the diff: agent turns cache the prompt and page any remainder via read_diff, so the agent
    # inlines ~5k diff lines while single-shot models keep the one-request ceiling
    prompt_chars = REVIEW_PROMPT_CHARS * (2 if is_agent_review_model else 1)
    diff_budget = max(1000, prompt_chars - len(guidelines_section) - len(full_files_section) - len(history_section))
    diff_truncated = len(augmented_diff) > diff_budget
    if is_agent_review_model:  # must match the get_agent_response fallback gate
        visibility_section = (  # function tools carry their own schema descriptions; only cross-tool rules belong here
            "EVIDENCE - every finding needs it:\n"
            "- Start from the diff, then read the enclosing function, definitions, callers, and existing patterns before judging a hunk\n"
            "- A claim that a name, import, or reference in this repository is missing or wrong requires reading the file first\n"
            "- Do not flag package or version availability based on web search. Only report it when the diff supplies "
            "authoritative resolver or failing CI evidence; otherwise dependency installation or CI owns that check\n"
            "- A claim about anything else outside this repository (external identifiers, API parameters, vendor "
            "behavior) requires web_search first: your knowledge predates this PR, so let current docs settle it "
            "either way - an official source that lacks what the diff uses is evidence against it, and a claim the "
            "search does not settle is not a finding\n"
            "- Batch independent tool calls into one turn (turns and cost are budgeted) and never quote large tool output back\n"
            "- If PROJECT GUIDELINES (CLAUDE.md/AGENTS.md) are provided, respect project-specific conventions and standards\n\n"
        )
    else:
        visibility_section = (
            "LIMITED VISIBILITY - IMPORTANT:\n"
            "- You see only the diff and partial file contents, and you cannot verify anything beyond them\n"
            "- Assume the author is knowledgeable about: new package versions, imports to functions defined elsewhere, dependencies, and codebase architecture\n"
            "- Do NOT flag what you cannot confirm from the diff or the file contents provided: external names, versions, or behavior; imports that appear unused; references to code you cannot see\n"
            "- If unsure whether something is an error, assume the author knows what they're doing\n"
            "- If PROJECT GUIDELINES (CLAUDE.md/AGENTS.md) are provided, respect project-specific conventions and standards\n\n"
        )

    continuity_section = ""
    if prior_reviews:
        continuity_section = (
            f"CONTINUITY - you already reviewed this PR {len(prior_reviews)} time(s), this is review "
            f"{len(prior_reviews) + 1}:\n"
            "- PRIOR REVIEWS below carries your earlier summaries and findings plus the replies to them; the diff "
            "shows the current state\n"
            "- Never contradict yourself without cause: a change made to satisfy an earlier finding is not a new "
            "problem, and an earlier finding is reversed only with concrete new evidence, stated as such with the "
            "review number it reverses\n"
            "- Drop findings the current diff resolves; repeat an unresolved one only while it still applies, since "
            "its inline comment was deleted with the superseded review\n"
            "- A reply under 'Replies to your findings' that rejects or explains one settles it: do not raise it "
            "again. Everything under 'Other review comments' is context, not a verdict on your findings\n"
            + (
                "- Call read_pr_conversation before repeating or reversing a finding, and whenever the excerpt below "
                "is truncated\n"
                if is_agent_review_model
                else ""
            )
            + "- Open the summary with what changed since the last review: addressed, still open, newly introduced\n\n"
        )

    content = (
        "You are an expert code reviewer for Ultralytics. Review code changes and provide inline comments ONLY for genuine issues.\n\n"
        "WHEN TO COMMENT (priority order):\n"
        "- Security vulnerabilities, data loss, corruption, or irreversible behavior\n"
        "- Bugs, broken contracts, race conditions, and compatibility regressions with a concrete failure path\n"
        "- Performance regressions with a plausible workload and measurable impact\n"
        "- Never approve any added file larger than 1 MB, regardless of type\n"
        "- Maintainability only when the change creates demonstrated duplication, conflicting owners, or unreachable behavior\n\n"
        "WHEN NOT TO COMMENT:\n"
        "- Style/formatting (handled by ruff/prettier)\n"
        "- Minor naming preferences\n"
        "- Generic best practices, defensive guards for impossible states, or 'consider using X' without a concrete defect\n"
        "- Missing tests unless a high-risk regression path is uncovered and existing coverage does not exercise it\n"
        "- Issues in unchanged context lines\n\n"
        f"{visibility_section}"
        f"{continuity_section}"
        "QUALITY OVER QUANTITY:\n"
        "- Zero comments is valid for clean PRs: never invent an issue, never withhold an evidence-backed one\n"
        "- Before commenting, trace the changed value or control flow through its owner, callers, and tests; use repository tools when the diff alone cannot prove the claim\n"
        "- Each comment must identify the triggering scenario, resulting incorrect behavior, and smallest owner-level correction\n"
        "- Severity: CRITICAL enables compromise or broad irreversible loss; HIGH breaks a core path or loses data; MEDIUM breaks a realistic edge path; LOW is a bounded defect; SUGGESTION is non-blocking\n"
        "- Combine related issues into one comment\n"
        f"- Hard cap: {MAX_REVIEW_COMMENTS} comments maximum\n\n"
        "SUGGESTIONS:\n"
        "- Provide 'suggestion' field with ready-to-merge code when you can confidently fix the issue\n"
        "- Suggestions must be complete, working code with NO comments, placeholders, or explanations\n"
        "- Single-line fixes only: provide 'suggestion' without 'start_line' to replace the line at 'line'\n"
        "- Match the exact indentation of the original code\n"
        "- Avoid triple backticks (```) in suggestions as they break Markdown formatting\n\n"
        "SUMMARY: state the reviewed scope, the behavioral verdict, and any remaining risk in concise prose; say LGTM plainly when the PR is clean.\n\n"
        "DIFF LINE FORMAT (how to read line numbers):\n"
        '  R  123 +code here      <- \'R\' means RIGHT (new file), number is 123, use {"line": 123, "side": "RIGHT"}\n'
        '  L   45 -code here      <- \'L\' means LEFT (old file), number is 45, use {"line": 45, "side": "LEFT"}\n'
        "         context         <- no prefix = unchanged context, don't comment on these\n"
        "- Suggestions ONLY work on RIGHT (added) lines, never LEFT (removed) lines\n"
        "- ONLY use line numbers you see explicitly prefixed with R or L in the initial diff"
        f"{' or read_diff output' if is_agent_review_model else ''}\n\n"
        "Return JSON: "
        '{"comments": [{"file": "exact/path", "line": N, "side": "RIGHT", "severity": "HIGH", "message": "..."}], "summary": "..."}\n\n'
        "JSON rules: exact paths (no ./), severity: CRITICAL|HIGH|MEDIUM|LOW|SUGGESTION\n"
        f"Files changed: {len(file_list)} ({', '.join(file_list[:30])}{'...' if len(file_list) > 30 else ''}), Lines: {lines_changed}\n"
        f"{'Large PR: the diff below is truncated. ' if diff_truncated else ''}"
        f"{'Use list_changed_files and read_diff to inspect changed files not shown in the initial prompt. ' if diff_truncated and is_agent_review_model else ''}\n"
    )

    messages = [
        {"role": "system", "content": content},
        {
            "role": "user",
            "content": (
                f"Review this PR in https://github.com/{repository}:\n\n"
                f"TITLE:\n{pr_title}\n\n"
                f"BODY:\n{remove_html_comments(pr_description or '')[:8000]}\n\n"
                f"{guidelines_section}"
                f"{history_section}"
                f"{full_files_section}"
                f"DIFF:\n{augmented_diff[:diff_budget]}\n\n"
                "Now review this diff according to the rules above. Return JSON with comments array and summary."
            ),
        },
    ]

    # Debug output for ultralytics/actions repo
    if repository == "ultralytics/actions":
        print(f"\nSystem prompt ({len(messages[0]['content'])} chars):\n{messages[0]['content']}\n")
        print(f"\nUser prompt ({len(messages[1]['content'])} chars):\n{messages[1]['content']}\n")

    try:
        schema = {
            "type": "object",
            "properties": {
                "comments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "line": {"type": "integer"},
                            "side": {"type": "string", "enum": ["LEFT", "RIGHT"]},
                            "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "SUGGESTION"]},
                            "message": {"type": "string"},
                            "start_line": {"type": ["integer", "null"]},
                            "suggestion": {"type": ["string", "null"]},
                        },
                        "required": ["file", "line", "side", "severity", "message", "start_line", "suggestion"],
                        "additionalProperties": False,
                    },
                },
                "summary": {"type": "string"},
            },
            "required": ["comments", "summary"],
            "additionalProperties": False,
        }

        tools, tool_handlers = build_review_agent_tools(
            diff_files, augmented_diff, event, head_sha, local_checkout, review_history
        )
        response = get_agent_response(
            messages,
            text_format={"format": {"type": "json_schema", "name": "pr_review", "strict": True, "schema": schema}},
            model=review_model,
            reasoning_effort="high",
            tools=tools,
            tool_handlers=tool_handlers,
            max_turns=MAX_AGENT_TURNS,
            max_cost=REVIEW_COST_SOFT_LIMIT,
            parallel_tools=True,  # review tools are read-only GitHub/diff reads, safe to batch concurrently
            retries=1,  # one transient failure on any of the sequential turns would otherwise abort the whole review
            # Do not pass background=True; queued background reviews can consume the full 900s poll timeout.
        )

        # Sanitize leaked tool-citation tokens from model output
        response["summary"] = sanitize_ai_text(response.get("summary", ""))
        for c in response.get("comments", []):
            if "message" in c:
                c["message"] = sanitize_ai_text(c["message"])

        print(json.dumps(response, indent=2))

        # Count comments BEFORE filtering (for COMMENT vs APPROVE decision)
        comments_before_filtering = len(response.get("comments", []))
        print(f"AI generated {comments_before_filtering} comments")

        # Validate, filter, and deduplicate comments
        unique_comments = {}
        for c in response.get("comments", []):
            file_path, line_num = c.get("file"), c.get("line", 0)
            start_line = c.get("start_line")
            side = (c.get("side") or "RIGHT").upper()  # Default to RIGHT (added lines)

            # Validate line numbers are in diff (check appropriate side)
            if file_path not in diff_files:
                print(f"Filtered out {file_path}:{line_num} (file not in diff)")
                continue

            side_map = diff_files[file_path].get(side, {})
            hunk_map = diff_files[file_path].get("_HUNK", {}).get(side, {})

            if line_num not in side_map:
                available = {s: list(diff_files[file_path][s].keys())[:10] for s in ["RIGHT", "LEFT"]}
                print(f"Filtered out {file_path}:{line_num} (side={side}, available: {available})")
                continue

            # GitHub rejects suggestions on removed lines
            if side == "LEFT" and c.get("suggestion"):
                print(f"Dropping suggestion for {file_path}:{line_num} - LEFT side doesn't support suggestions")
                c.pop("suggestion", None)

            # Enforce same-hunk multi-line selection; otherwise drop start_line
            if start_line:
                if c.get("suggestion"):
                    # Multi-line suggestions need start_line to define the range - drop both if invalid
                    suggestion_text = c.get("suggestion", "")
                    if "\n" in suggestion_text:
                        print(
                            f"Dropping multi-line suggestion for {file_path}:{line_num} - range required but start_line invalid"
                        )
                        c.pop("suggestion", None)
                    print(f"Dropping start_line for {file_path}:{line_num} - single-line comments only")
                    c.pop("start_line", None)
                elif start_line >= line_num:
                    print(f"Invalid start_line {start_line} >= line {line_num} for {file_path}, dropping start_line")
                    c.pop("start_line", None)
                elif start_line not in side_map:
                    print(f"start_line {start_line} not in diff for {file_path}, dropping start_line")
                    c.pop("start_line", None)
                elif hunk_map.get(start_line) != hunk_map.get(line_num):
                    print(
                        f"start_line {start_line} not in same hunk as line {line_num} for {file_path}, dropping start_line"
                    )
                    c.pop("start_line", None)

            # Deduplicate by line number and side
            key = f"{file_path}:{side}:{line_num}"
            if key not in unique_comments:
                unique_comments[key] = c
            else:
                print(f"⚠️  AI duplicate for {key}: {c.get('severity')} - {(c.get('message') or '')[:60]}...")

        filtered_comments = list(unique_comments.values())
        filtered_comments.sort(
            key=lambda c: (
                SEVERITY_RANK.get(c.get("severity")),
                c.get("file") or "",
                c.get("line", 0),
            )
        )
        if len(filtered_comments) > MAX_REVIEW_COMMENTS:
            print(f"Trimming comments from {len(filtered_comments)} to {MAX_REVIEW_COMMENTS}")
            filtered_comments = filtered_comments[:MAX_REVIEW_COMMENTS]

        response.update(
            {
                "comments": filtered_comments,
                "comments_before_filtering": comments_before_filtering,
                "diff_files": diff_files,
                "diff_truncated": diff_truncated,
                "skipped_files": skipped_files,
                "head_sha": head_sha,
            }
        )
        print(f"Valid comments after filtering: {len(response['comments'])}")
        return response

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"Review generation failed: {e}\n{error_details}")
        summary = (
            f"{ERROR_MARKER}: `{type(e).__name__}`\n\n"
            f"<details><summary>Debug Info</summary>\n\n```\n{error_details}\n```\n</details>"
        )
        return {"comments": [], "summary": summary, "head_sha": head_sha}


def get_local_head_sha() -> str | None:
    """Get the current HEAD SHA from local git repo."""
    import subprocess

    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Failed to get local HEAD SHA: {e}")
        return None


def _verified_local_checkout(head_sha: str | None) -> bool:
    """Check the working tree is a clean checkout of the PR head (formatters may dirty it before reviews run)."""
    import subprocess

    if not head_sha or get_local_head_sha() != head_sha:
        return False
    try:
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        return not status.stdout.strip()
    except Exception:
        return False


def clear_previous_review(event: Action) -> dict:
    """Capture the bot's prior reviews, then dismiss their decisions and delete their superseded inline comments."""
    pr_number, bot_username = event.pr.get("number"), event.get_username()
    reviews_base = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    reviews = event.paginate(reviews_base, hard=True)
    owned = [
        review
        for review in reviews
        if review.get("user", {}).get("login") == bot_username and REVIEW_MARKER in (review.get("body") or "")
    ]
    comments_base = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/comments"
    comments = event.paginate(comments_base, hard=True)
    history = _build_review_history(owned, comments, bot_username)  # capture responses before deleting the comments

    owned_reviews = {review["id"] for review in owned}
    for review in owned:
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED"):
            event.put(
                f"{reviews_base}/{review['id']}/dismissals",
                json={"message": "Superseded by new review"},
                hard=True,
            )
    for comment in comments:
        if comment.get("pull_request_review_id") in owned_reviews:  # 404: already deleted by a person or another run
            url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/comments/{comment['id']}"
            event.delete(url, expected_status=[200, 204, 404], hard=True)
    return history


def post_review_summary(event: Action, review_data: dict, review_number: int = 1) -> None:
    """Post overall review summary and inline comments as a single PR review."""
    if not (pr_number := event.pr.get("number")):
        return

    commit_sha = review_data["head_sha"]
    if head_moved := event.get_pr_head_sha() != commit_sha:
        print(f"PR head moved during review; anchoring findings to reviewed commit {commit_sha[:7]}")

    comments = review_data.get("comments", [])
    summary = review_data.get("summary") or ""

    # Don't approve if error occurred, head moved, inline comments exist, or medium-or-higher severity issues
    has_error = not summary or ERROR_MARKER in summary
    has_evidence = bool(review_data.get("diff_files"))
    has_inline_comments = review_data.get("comments_before_filtering", 0) > 0
    has_issues = any(c.get("severity") not in ["LOW", "SUGGESTION", None] for c in comments)
    event_type = (
        "COMMENT"
        if (
            has_error
            or head_moved
            or not has_evidence
            or has_inline_comments
            or has_issues
            or review_data.get("diff_truncated")
            or review_data.get("oversized_files")
            or review_data.get("unverified_sizes")
        )
        else "APPROVE"
    )

    title = REVIEW_MARKER if review_number < 2 else f"{REVIEW_MARKER} {review_number}"  # first review carries no number
    body = f"{title}\n\n{ACTIONS_CREDIT}\n\n{summary[:3000]}\n\n"

    if comments:
        # Log findings in the review body: inline comments are deleted when the next review supersedes this one
        findings = "\n".join(
            f"- {EMOJI_MAP.get(c.get('severity'), '💭')} **{c.get('severity') or 'SUGGESTION'}** "
            f"`{c.get('file')}:{c.get('line')}` {_clip((c.get('message') or '').strip(), MAX_FINDING_LOG_CHARS)}"
            for c in comments
        )
        summary_text = f"💬 Posted {len(comments)} inline comment{'s' if len(comments) != 1 else ''}"
        body += f"<details><summary>{summary_text}</summary>\n\n{findings}\n</details>\n"

    if review_data.get("diff_truncated"):
        body += "\n⚠️ **Large PR**: Review focused on critical issues. Some details may not be covered.\n"

    body += format_skipped_files_dropdown(review_data.get("skipped_files", []))

    # Build inline comments for the review
    review_comments = []
    for comment in comments:
        if not (file_path := comment.get("file")) or not (line := comment.get("line", 0)):
            continue

        severity = comment.get("severity") or "SUGGESTION"
        side = comment.get("side", "RIGHT")
        comment_body = f"{EMOJI_MAP.get(severity, '💭')} **{severity}**: {(comment.get('message') or '')[:3000]}"

        if suggestion := comment.get("suggestion"):
            suggestion = suggestion[:3000]  # Clip suggestion length
            if "```" not in suggestion:
                # Extract original line indentation and apply to suggestion
                if original_line := review_data.get("diff_files", {}).get(file_path, {}).get(side, {}).get(line):
                    indent = len(original_line) - len(original_line.lstrip())
                    suggestion = " " * indent + suggestion.strip()
                comment_body += f"\n\n**Suggested change:**\n```suggestion\n{suggestion}\n```"

        # Build comment with optional start_line for multi-line context
        review_comment = {"path": file_path, "line": line, "body": comment_body, "side": side}
        if (start_line := comment.get("start_line")) and start_line < line:
            review_comment["start_line"] = start_line
            review_comment["start_side"] = side

        review_comments.append(review_comment)

    # Submit review with inline comments
    url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    payload = {"commit_id": commit_sha, "body": body.strip(), "event": event_type}
    if review_comments:
        # One anchor GitHub cannot resolve rejects the whole review; the body logs every finding, so post it alone
        response = event.post(url, json={**payload, "comments": review_comments}, expected_status=[200, 422], hard=True)
        if response.status_code != 422:
            return
        print("GitHub rejected the inline comments; posting the review body alone")
    event.post(url, json=payload, hard=True)


def run_review(event: Action, pr_title: str, pr_description: str) -> None:
    """Supersede prior reviews, then generate and publish the next numbered review of the PR head."""
    try:
        diff, head_sha = event.get_pr_diff_snapshot()
    except RuntimeError as e:
        print(f"Skipping stale PR review: {e}")
        return
    history = clear_previous_review(event)
    review = generate_pr_review(event.repository, diff, pr_title, pr_description, event, head_sha, history)
    post_review_summary(event, review, review_number=len(history["reviews"]) + 1)
    print("PR review completed")


def main(*args, **kwargs):
    """Main entry point for PR review action."""
    event = Action(*args, **kwargs)

    # Handle review requests
    if event.event_name == "pull_request" and event.event_data.get("action") == "review_requested":
        if event.event_data.get("requested_reviewer", {}).get("login") != event.get_username():
            return
        print(f"Review requested from {event.get_username()}")

    if not event.pr or event.pr.get("state") != "open":
        print(f"Skipping: PR state is {event.pr.get('state') if event.pr else 'None'}")
        return

    # Skip self-authored or bot PRs unless manually review_requested
    if event.event_data.get("action") != "review_requested" and event.should_skip_pr_author():
        return

    print(f"Starting PR review for #{event.pr['number']}")
    run_review(event, event.pr.get("title") or "", event.pr.get("body") or "")


if __name__ == "__main__":
    main()
