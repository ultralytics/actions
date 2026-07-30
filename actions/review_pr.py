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
MAX_CONTEXT_FILE_CHARS = 5000
MAX_REVIEW_COMMENTS = 8
MAX_TOOL_OUTPUT_CHARS = 20000
MAX_TOOL_FILE_LINES = 240
MAX_AGENT_TURNS = 16
REVIEW_COST_SOFT_LIMIT = 2.00  # stop requesting tools after cumulative spend reaches this amount
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SUGGESTION": 4, None: 5}
MAX_THREADS_SECTION_CHARS = 8000

GRAPHQL_PR_REVIEW_THREADS = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
    repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
            reviewThreads(first: 100, after: $cursor) {
                pageInfo { hasNextPage endCursor }
                nodes {
                    id
                    isResolved
                    isOutdated
                    diffSide
                    path
                    line
                    root: comments(first: 1) {
                        nodes {
                            fullDatabaseId
                            author { login }
                            body
                            pullRequestReview { body }
                        }
                    }
                    latest: comments(last: 30) {
                        nodes {
                            fullDatabaseId
                            author { login }
                            body
                        }
                    }
                }
            }
        }
    }
}
"""

GRAPHQL_RESOLVE_REVIEW_THREAD = """
mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
        thread { id }
    }
}
"""


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
        if target.stat().st_size > 500_000:
            raise RuntimeError(f"{path} is too large to read")
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
) -> tuple[list[dict], dict]:
    """Build read-only tools for the PR review agent, reading files from the PR head via the GitHub API."""
    diff_files = diff_files or {}
    diff_chunks = _split_augmented_diff_by_file(augmented_diff)
    head_tree = []  # cached PR head file listing

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
        "search_repo": search_repo,
        "list_files": list_files,
    }
    if not local_checkout:  # repo text search needs a checkout of the PR head; drop it instead of returning empty
        tools = [t for t in tools if t.get("name") != "search_repo"]
        del handlers["search_repo"]
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


def format_review_threads(threads: dict[str, dict]) -> tuple[str, set[str]]:
    """Format unresolved review threads as a bounded prompt section, returning the refs actually shown."""
    blocks, shown, total = [], set(), 0
    for ref, thread in threads.items():
        anchor = f"{thread['path']}:{thread['line']} ({thread['side']})" if thread.get("line") else thread["path"]
        outdated = " [outdated: the anchored code changed since]" if thread["outdated"] else ""
        comments = thread["comments"]
        if len(comments) > 7:  # root finding plus the newest replies; 7 clipped comments always fit the budget
            comments = [comments[0], *comments[-6:]]
        convo = "\n".join(f"  {c['author']}: {_clip_tool_output(c['body'], 1000)}" for c in comments)
        block = f"[{ref}] {anchor}{outdated}\n{convo}"
        if total + len(block) > MAX_THREADS_SECTION_CHARS and blocks:  # whole threads only, never cut mid-thread
            print(f"Dropping {len(threads) - len(shown)} review threads from prompt (section budget)")
            break
        blocks.append(block)
        shown.add(ref)
        total += len(block) + 2
    if not blocks:
        return "", shown
    section = "\n\n".join(blocks)
    return (
        f"EXISTING REVIEW THREADS (your unresolved findings from previous reviews, with replies):\n{section}\n\n",
        shown,
    )


def generate_pr_review(
    repository: str,
    diff_text: str,
    pr_title: str,
    pr_description: str,
    event: Action = None,
    head_sha: str | None = None,
    threads: dict[str, dict] | None = None,
    settled: list[str] | None = None,
) -> dict:
    """Generate comprehensive PR review with line-specific comments and overall assessment."""
    head_sha = head_sha or (event.get_pr_head_sha() if event else None)
    if diff_text.startswith("ERROR:"):
        return {"comments": [], "summary": f"{ERROR_MARKER}: {diff_text}", "head_sha": head_sha}
    if not diff_text:
        return {"comments": [], "summary": "No changes detected in diff", "head_sha": head_sha}

    diff_files, augmented_diff = parse_diff_files(diff_text)
    if not diff_files:
        return {"comments": [], "summary": "No reviewable text changes detected in diff", "head_sha": head_sha}

    # Filter out generated/vendored files
    filtered_files = {p: s for p, s in diff_files.items() if not should_skip_file(p)}
    skipped_files = [p for p in diff_files if p not in filtered_files]
    diff_files = filtered_files

    if not diff_files:
        return {
            "comments": [],
            "summary": f"All {len(skipped_files)} changed files are generated/vendored (skipped review)",
            "skipped_files": skipped_files,
            "head_sha": head_sha,
        }

    file_list = list(diff_files.keys())
    lines_changed = sum(len(sides["RIGHT"]) + len(sides["LEFT"]) for sides in diff_files.values())

    # Read model-appropriate guidelines from the PR head for project-specific review context
    review_model = get_review_model()
    is_agent_review_model = not _is_anthropic_model(review_model)
    local_checkout = _verified_local_checkout(head_sha)
    if head_sha:
        print(f"Reviewing PR head {head_sha[:7]} ({'local checkout' if local_checkout else 'via GitHub API'})")
    guidelines_section = get_repo_guidelines(review_model, event, head_sha, local_checkout)

    # Fetch full file contents for better context if within token budget
    full_files_section = ""
    if event and head_sha and not is_agent_review_model and len(file_list) <= 10:  # Reasonable file count limit
        file_contents, total_chars = [], len(augmented_diff) + len(guidelines_section)
        for file_path in file_list:  # already filtered by should_skip_file above
            text = _read_head_file(event, head_sha, local_checkout, file_path) or ""
            if not text or len(text) > 100_000:  # skip missing and >100KB files entirely
                continue
            snippet = text[:MAX_CONTEXT_FILE_CHARS]
            if len(snippet) == MAX_CONTEXT_FILE_CHARS:
                snippet = f"{snippet.rstrip()}\n... (truncated)"
            # Only include if within budget, include buffer for Markdown noise
            estimated_cost = len(snippet) + 200
            if total_chars + estimated_cost >= MAX_PROMPT_CHARS:
                break  # Stop when we hit budget limit
            file_contents.append(f"### {file_path}\n```\n{snippet}\n```")
            total_chars += estimated_cost
        if file_contents:
            full_files_section = f"FULL FILE CONTENTS:\n{chr(10).join(file_contents)}\n\n"

    threads = threads or {}
    threads_section, shown_threads = format_review_threads(threads)
    settled_section = (
        "SETTLED FINDINGS (resolved in earlier rounds - do not re-raise or rehash them in any form):\n"
        + "\n".join(f"- {s}" for s in settled[:20])
        + "\n\n"
        if settled
        else ""
    )

    # Calculate remaining budget for diff and check if truncation needed
    diff_budget = max(
        1000,
        MAX_PROMPT_CHARS
        - len(guidelines_section)
        - len(full_files_section)
        - len(threads_section)
        - len(settled_section),
    )
    diff_truncated = len(augmented_diff) > diff_budget
    is_large_pr = diff_truncated or len(file_list) > 30
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

    threads_rules = (
        (
            "EXISTING REVIEW THREADS:\n"
            "- The user prompt lists your unresolved threads from previous reviews with any replies to them\n"
            "- Re-check every thread against the current code first: 'resolve' when the code now addresses the "
            "issue or a reply rebuts it on substance - never leave an addressed thread unresolved. 'reply' when the "
            "finding still stands and a reply deserves an answer; omit the thread only when it still stands and "
            "there is nothing new to say\n"
            "- Judge each thread by its original finding: once its substantive risk is addressed, resolve - do not "
            "pivot the thread to a narrower residue of the same concern\n"
            "- Accept a rebuttal only when it is technically substantiated (code, docs, measurements) - confident "
            "assertion alone changes nothing\n"
            "- A 'reply' that keeps a finding alive must cite the current code (path and line) that sustains it; "
            "if you cannot cite it, resolve\n"
            "- Two replies per thread is the debate limit: if the author still disagrees after your second reply, "
            "resolve with a brief dissent note for the record or leave the thread to the author - further argument "
            "is not available\n"
            "- Never post a new comment for an issue that already has a thread - use a 'reply' thread action instead\n"
            "- 'message' is posted as a reply in the thread: required for 'reply', a brief reason or empty for 'resolve'\n\n"
        )
        if threads
        else ""
    )

    content = (
        "You are an expert code reviewer for Ultralytics. Review code changes and provide inline comments ONLY for genuine issues.\n\n"
        "WHEN TO COMMENT (priority order):\n"
        "- Bugs and logic errors that will cause failures\n"
        "- Performance issues with measurable impact\n"
        "- Code best practices and maintainability\n"
        "- Missing error handling for likely failure cases\n"
        "- Security issues (only obvious vulnerabilities, not speculative)\n\n"
        "WHEN NOT TO COMMENT:\n"
        "- Style/formatting (handled by ruff/prettier)\n"
        "- Minor naming preferences\n"
        "- 'Consider using X' without clear benefit\n"
        "- Issues in unchanged context lines\n"
        "- Residual hardening of a risk the code already guards: if the remaining worst case is a degraded message, "
        "a cosmetic inaccuracy, or a narrower rerun of an addressed concern, it is not a finding - findings must "
        "clear the same minimal-scope bar the PROJECT GUIDELINES set for code changes\n\n"
        f"{visibility_section}"
        "QUALITY OVER QUANTITY:\n"
        "- Zero comments is valid for clean PRs: never invent an issue, never withhold an evidence-backed one\n"
        "- Each comment must be actionable with clear reasoning\n"
        "- Combine related issues into one comment\n"
        "- Severity reflects the worst realistic consequence: CRITICAL/HIGH require wrong behavior, data loss, "
        "security exposure, or wrong merge decisions; degraded messages, rare-race cosmetics, and hardening "
        "suggestions are LOW or SUGGESTION\n"
        f"- Hard cap: {MAX_REVIEW_COMMENTS} comments maximum\n\n"
        "SUGGESTIONS:\n"
        "- Provide 'suggestion' field with ready-to-merge code when you can confidently fix the issue\n"
        "- Suggestions must be complete, working code with NO comments, placeholders, or explanations\n"
        "- Single-line fixes only: provide 'suggestion' without 'start_line' to replace the line at 'line'\n"
        "- Match the exact indentation of the original code\n"
        "- Avoid triple backticks (```) in suggestions as they break Markdown formatting\n\n"
        f"{threads_rules}"
        "SUMMARY: brief overall assessment of what's good and what needs attention; say so plainly when the PR is clean.\n\n"
        "DIFF LINE FORMAT (how to read line numbers):\n"
        '  R  123 +code here      <- \'R\' means RIGHT (new file), number is 123, use {"line": 123, "side": "RIGHT"}\n'
        '  L   45 -code here      <- \'L\' means LEFT (old file), number is 45, use {"line": 45, "side": "LEFT"}\n'
        "         context         <- no prefix = unchanged context, don't comment on these\n"
        "- Suggestions ONLY work on RIGHT (added) lines, never LEFT (removed) lines\n"
        "- ONLY use line numbers you see explicitly prefixed with R or L in the initial diff"
        f"{' or read_diff output' if is_agent_review_model else ''}\n\n"
        "Return JSON: "
        '{"comments": [{"file": "exact/path", "line": N, "side": "RIGHT", "severity": "HIGH", "message": "..."}], '
        '"summary": "...", "thread_actions": [{"thread": "T1", "action": "resolve", "message": "..."}]}\n'
        "thread_actions must be [] when no existing review threads are listed\n\n"
        "JSON rules: exact paths (no ./), severity: CRITICAL|HIGH|MEDIUM|LOW|SUGGESTION\n"
        f"Files changed: {len(file_list)} ({', '.join(file_list[:30])}{'...' if len(file_list) > 30 else ''}), Lines: {lines_changed}\n"
        f"{'Large or truncated PR: the diff below is incomplete. ' if is_large_pr else ''}"
        f"{'Use list_changed_files and read_diff to inspect changed files not shown in the initial prompt. ' if is_large_pr and is_agent_review_model else ''}\n"
    )

    messages = [
        {"role": "system", "content": content},
        {
            "role": "user",
            "content": (
                f"Review this PR in https://github.com/{repository}:\n\n"
                f"TITLE:\n{pr_title}\n\n"
                f"BODY:\n{remove_html_comments(pr_description or '')[:1000]}\n\n"
                f"{guidelines_section}"
                f"{full_files_section}"
                f"{threads_section}"
                f"{settled_section}"
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
                "thread_actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "thread": {"type": "string"},
                            "action": {"type": "string", "enum": ["resolve", "reply"]},
                            "message": {"type": "string"},
                        },
                        "required": ["thread", "action", "message"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["comments", "summary", "thread_actions"],
            "additionalProperties": False,
        }

        tools, tool_handlers = build_review_agent_tools(diff_files, augmented_diff, event, head_sha, local_checkout)
        response = get_agent_response(
            messages,
            text_format={"format": {"type": "json_schema", "name": "pr_review", "strict": True, "schema": schema}},
            model=review_model,
            reasoning_effort="medium",
            tools=tools,
            tool_handlers=tool_handlers,
            max_turns=MAX_AGENT_TURNS,
            max_cost=REVIEW_COST_SOFT_LIMIT,
            parallel_tools=True,  # review tools are read-only GitHub/diff reads, safe to batch concurrently
            request_timeout=(30, 120),
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
        thread_anchors = {
            (t["path"], t["side"], t["line"]): SEVERITY_RANK.get(t.get("severity") or "CRITICAL", 0)
            for t in threads.values()
            if t.get("line")
        }
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

            # An existing thread anchors here: only a strictly more severe new finding may share the anchor
            anchor_rank = thread_anchors.get((file_path, side, line_num))
            if anchor_rank is not None and SEVERITY_RANK.get(c.get("severity"), 5) >= anchor_rank:
                print(f"Filtered out {file_path}:{line_num} (existing review thread anchors here)")
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

        # Validate thread actions against the threads shown to the model, first action per thread wins
        thread_actions = {}
        for action in response.get("thread_actions", []):
            ref, verb = action.get("thread"), action.get("action")
            message = sanitize_ai_text(action.get("message") or "").strip()
            if (
                ref not in shown_threads  # never act on a thread the model was not shown
                or ref in thread_actions
                or verb not in ("resolve", "reply")  # the Anthropic fallback does not enforce the schema enum
                or (verb == "reply" and not message)
            ):
                print(f"Filtered out thread action {ref}: {verb}")
                continue
            # Never reply on top of the bot's own last word: without a new human reply there is nothing to answer
            comments = threads[ref]["comments"]
            if verb == "reply" and comments[-1]["author"] == comments[0]["author"]:
                print(f"Filtered out thread action {ref}: reply (no new replies since the bot's last comment)")
                continue
            # Two standing replies end the debate: from here the bot may only concede or leave it to the author
            if verb == "reply" and sum(c["author"] == comments[0]["author"] for c in comments[1:]) >= 2:
                print(f"Filtered out thread action {ref}: reply (debate limit reached, resolve or stand aside)")
                continue
            thread_actions[ref] = {"thread": ref, "action": verb, "message": message}
        # Only findings-level threads gate approval: LOW/SUGGESTION threads advise without blocking
        blocking = {ref for ref, t in threads.items() if t.get("severity") not in ("LOW", "SUGGESTION")}
        resolved = {ref for ref, a in thread_actions.items() if a["action"] == "resolve"}

        response.update(
            {
                "comments": filtered_comments,
                "comments_before_filtering": comments_before_filtering,
                "thread_actions": list(thread_actions.values()),
                "open_threads": len(blocking - resolved),
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


def dismiss_previous_reviews(event: Action) -> None:
    """Dismiss the bot's stale review decisions so an outdated APPROVED state never counts for new commits."""
    pr_number, bot_username = event.pr.get("number"), event.get_username()
    reviews_base = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    reviews = event.get(reviews_base, params={"per_page": 100}, hard=True).json()
    for review in reviews:
        if (
            review.get("user", {}).get("login") == bot_username
            and REVIEW_MARKER in (review.get("body") or "")
            and review.get("state") in ("APPROVED", "CHANGES_REQUESTED")
        ):
            event.put(
                f"{reviews_base}/{review['id']}/dismissals",
                json={"message": "Superseded by new review"},
                hard=True,
            )


def get_review_threads(event: Action) -> tuple[dict[str, dict], list[str]]:
    """Fetch the bot's unresolved review threads keyed by short refs (T1, T2, ...), plus settled finding summaries."""
    if not (bot_username := event.get_username()):  # never degrade to "no threads": that re-creates duplicates
        raise RuntimeError("Failed to resolve bot username for review threads")
    threads, settled, cursor = {}, [], None
    while True:
        result = event.graphql_request(
            GRAPHQL_PR_REVIEW_THREADS,
            variables={"owner": event.owner, "name": event.repo_name, "number": event.pr["number"], "cursor": cursor},
        )
        if "data" not in result or result.get("errors"):
            raise RuntimeError(f"Review threads query failed: {result.get('errors')}")
        connection = (((result["data"] or {}).get("repository") or {}).get("pullRequest") or {}).get(
            "reviewThreads"
        ) or {}
        for node in connection.get("nodes") or []:
            root = ((node.get("root") or {}).get("nodes") or [{}])[0]
            if (root.get("author") or {}).get("login") != bot_username or REVIEW_MARKER not in (
                (root.get("pullRequestReview") or {}).get("body") or ""
            ):
                continue
            if node.get("isResolved"):
                settled.append((root.get("body") or "")[:200])  # remembered so settled findings are never re-raised
                continue
            comments = (node.get("latest") or {}).get("nodes") or []  # newest replies: the last-word guard needs them
            if not comments or comments[0].get("fullDatabaseId") != root.get("fullDatabaseId"):
                comments = [root, *comments]  # thread longer than the fetched tail: keep the root finding visible
            severity = re.match(r"\S+ \*\*(\w+)\*\*:", root.get("body") or "")  # posted as "{emoji} **{severity}**:"
            threads[f"T{len(threads) + 1}"] = {
                "id": node["id"],
                "root_comment_id": root.get("fullDatabaseId"),
                "path": node.get("path"),
                "line": node.get("line"),
                "side": node.get("diffSide") or "RIGHT",
                "outdated": bool(node.get("isOutdated")),
                "severity": severity.group(1) if severity else None,
                "comments": [
                    {"author": (c.get("author") or {}).get("login") or "unknown", "body": c.get("body") or ""}
                    for c in comments
                ],
            }
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return threads, settled
        cursor = page_info.get("endCursor")


def apply_thread_actions(event: Action, review_data: dict, threads: dict[str, dict]) -> None:
    """Reply to and resolve existing review threads as decided by the review model."""
    if not (actions := review_data.get("thread_actions")):
        return
    if event.get_pr_head_sha() != review_data["head_sha"]:  # don't mutate threads from a stale review
        raise RuntimeError("PR head changed during review generation")
    fresh = {t["id"]: t["comments"] for t in get_review_threads(event)[0].values()}
    pr_number = event.pr["number"]
    applied = []
    for action in actions:
        thread = threads[action["thread"]]
        # New replies don't change the head SHA: never act on a conversation the model didn't see
        if fresh.get(thread["id"]) != thread["comments"]:
            print(f"Skipping {action['action']} on thread {thread['id']}: conversation changed during review")
            if action["action"] == "resolve" and thread.get("severity") not in ("LOW", "SUGGESTION"):
                review_data["open_threads"] += 1  # the thread stays open: keep the APPROVE gate honest
            continue
        if (message := action.get("message")) and (root_id := thread.get("root_comment_id")):
            event.post(
                f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/comments/{root_id}/replies",
                json={"body": message},
                hard=True,
            )
        if action["action"] == "resolve":
            result = event.graphql_request(GRAPHQL_RESOLVE_REVIEW_THREAD, variables={"threadId": thread["id"]})
            if "data" not in result or result.get("errors"):
                raise RuntimeError(f"Failed to resolve review thread {thread['id']}: {result}")
        applied.append(action)
    review_data["thread_actions"] = applied  # the summary's thread count reports only what actually happened


def post_review_summary(event: Action, review_data: dict) -> None:
    """Post overall review summary and inline comments as a single PR review."""
    if not (pr_number := event.pr.get("number")):
        return

    commit_sha = review_data["head_sha"]
    if event.get_pr_head_sha() != commit_sha:
        raise RuntimeError("PR head changed during review generation")

    comments = review_data.get("comments", [])
    summary = review_data.get("summary") or ""

    # Don't approve if error occurred, inline comments or open threads exist, or medium-or-higher severity issues
    has_error = not summary or ERROR_MARKER in summary
    has_evidence = bool(review_data.get("diff_files"))
    has_inline_comments = review_data.get("comments_before_filtering", 0) > 0
    has_open_threads = bool(review_data.get("open_threads"))
    has_issues = any(c.get("severity") not in ["LOW", "SUGGESTION", None] for c in comments)
    event_type = (
        "COMMENT"
        if (
            has_error
            or not has_evidence
            or has_inline_comments
            or has_open_threads
            or has_issues
            or review_data.get("diff_truncated")
        )
        else "APPROVE"
    )

    body = f"{REVIEW_MARKER}\n\n{ACTIONS_CREDIT}\n\n{summary[:3000]}\n\n"

    if comments:
        body += f"💬 Posted {len(comments)} inline comment{'s' if len(comments) != 1 else ''}\n"

    if thread_actions := review_data.get("thread_actions"):
        body += f"🧵 Updated {len(thread_actions)} existing review thread{'s' if len(thread_actions) != 1 else ''}\n"

    if comments or review_data.get("open_threads"):
        body += "🔁 Reply in the threads and re-request my review to continue the conversation\n"

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
    payload = {"commit_id": commit_sha, "body": body.strip(), "event": event_type}
    if review_comments:
        payload["comments"] = review_comments

    event.post(f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews", json=payload, hard=True)


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
    try:
        diff, head_sha = event.get_pr_diff_snapshot()
    except RuntimeError as e:
        print(f"Skipping stale PR review: {e}")
        return
    dismiss_previous_reviews(event)
    threads, settled = get_review_threads(event)
    if threads or settled:
        print(f"Found {len(threads)} unresolved and {len(settled)} settled review threads from previous reviews")
    review = generate_pr_review(
        event.repository,
        diff,
        event.pr.get("title") or "",
        event.pr.get("body") or "",
        event,
        head_sha,
        threads,
        settled,
    )
    apply_thread_actions(event, review, threads)  # before the summary, which claims these actions and may APPROVE
    post_review_summary(event, review)
    print("PR review completed")


if __name__ == "__main__":
    main()
