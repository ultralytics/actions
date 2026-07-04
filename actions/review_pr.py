# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path

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
MAX_AGENT_TURNS = 8
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SUGGESTION": 4, None: 5}


def _clip_tool_output(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Limit model-facing tool output size."""
    return text if len(text) <= limit else f"{text[:limit].rstrip()}\n... (truncated)"


def _resolve_repo_path(path: str) -> Path:
    """Resolve a repo-relative path without allowing access outside the checkout."""
    root = Path.cwd().resolve()
    target = (root / (path or ".")).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise ValueError(f"path must stay inside repository: {path}") from e
    return target


def read_file(path: str, start_line=None, end_line=None) -> str:
    """Read a bounded range from a repository file for agent review context."""
    try:
        target = _resolve_repo_path(path)
    except ValueError as e:
        return str(e)
    rel = target.relative_to(Path.cwd().resolve()).as_posix()
    if not target.is_file():
        return f"{path} is not a file."
    if should_skip_file(rel) or target.stat().st_size > 500_000:
        return f"{path} is skipped because it is generated, vendored, or too large."

    lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(1, int(start_line or 1))
    end = min(len(lines), int(end_line or len(lines)), start + MAX_TOOL_FILE_LINES - 1)
    if end < start:
        return f"{path} has no lines in requested range {start}-{end}."
    numbered = "\n".join(f"{i:>5}: {lines[i - 1]}" for i in range(start, end + 1))
    return _clip_tool_output(f"{rel}:{start}-{end}\n{numbered}")


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


def list_files(path_glob=None) -> str:
    """List repository files matching an optional glob."""
    files = [rel for _, rel in _iter_repo_files(path_glob)]
    if not files:
        return "No matching files found."
    return _clip_tool_output("\n".join(sorted(files)[:300]))


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


def build_review_agent_tools() -> tuple[list[dict], dict]:
    """Build read-only tools for the PR review agent."""
    tools = [
        {"type": "web_search"},
        {
            "type": "function",
            "name": "read_file",
            "description": (
                "Read a bounded line range from a repository file in the checked-out PR head, including unchanged "
                "files such as pyproject.toml, tests, configs, and shared helpers. Use this to verify changed code or "
                "nearby definitions before making a review finding."
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
    return tools, {"read_file": read_file, "search_repo": search_repo, "list_files": list_files}


def get_repo_guidelines(model: str = "") -> str:
    """Read guidelines from the repository root if they exist (one agent file + CONTRIBUTING.md)."""
    guidelines = []
    # Prefer CLAUDE.md for Anthropic models, AGENTS.md for others; load only one, never both
    agent_prefs = ("CLAUDE.md", "AGENTS.md") if "claude" in model.lower() else ("AGENTS.md", "CLAUDE.md")
    for filename in ("CONTRIBUTING.md", *agent_prefs):
        try:
            p = Path(filename)
            if p.is_file() and p.stat().st_size <= 100_000:
                content = p.read_text(encoding="utf-8", errors="ignore")[:MAX_CONTEXT_FILE_CHARS]
                if content:
                    guidelines.append(f"### {filename}\n~~~\n{content}\n~~~")
                    print(f"Loaded {filename} ({len(content)} chars) for review context")
                    if filename in agent_prefs:
                        break  # Only load one agent guidelines file
        except Exception as e:
            print(f"Failed to read {filename}: {e}")
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

    return files, "\n".join(augmented_lines)


def generate_pr_review(
    repository: str, diff_text: str, pr_title: str, pr_description: str, event: Action = None
) -> dict:
    """Generate comprehensive PR review with line-specific comments and overall assessment."""
    if not diff_text:
        return {"comments": [], "summary": "No changes detected in diff"}

    diff_files, augmented_diff = parse_diff_files(diff_text)
    if not diff_files:
        return {"comments": [], "summary": "No files with changes detected in diff"}

    # Filter out generated/vendored files
    filtered_files = {p: s for p, s in diff_files.items() if not should_skip_file(p)}
    skipped_files = [p for p in diff_files if p not in filtered_files]
    diff_files = filtered_files

    if not diff_files:
        return {
            "comments": [],
            "summary": f"All {len(skipped_files)} changed files are generated/vendored (skipped review)",
            "skipped_files": skipped_files,
        }

    file_list = list(diff_files.keys())
    lines_changed = sum(len(sides["RIGHT"]) + len(sides["LEFT"]) for sides in diff_files.values())

    # Read model-appropriate guidelines from repo root for project-specific review context
    review_model = get_review_model()
    is_agent_review_model = not _is_anthropic_model(review_model)
    guidelines_section = get_repo_guidelines(review_model)

    # Fetch full file contents for better context if within token budget
    full_files_section = ""
    if event and not is_agent_review_model and len(file_list) <= 10:  # Reasonable file count limit
        file_contents, total_chars = [], len(augmented_diff) + len(guidelines_section)
        for file_path in file_list:
            try:
                p = Path(file_path)
                if not p.is_file():
                    continue
                # Skip files matching SKIP_PATTERNS and files >100KB
                if should_skip_file(file_path) or p.stat().st_size > 100_000:
                    continue
                snippet = p.read_text(encoding="utf-8", errors="ignore")[:MAX_CONTEXT_FILE_CHARS]
                if not snippet:
                    continue
                if len(snippet) == MAX_CONTEXT_FILE_CHARS:
                    snippet = f"{snippet.rstrip()}\n... (truncated)"
                # Only include if within budget, include buffer for Markdown noise
                estimated_cost = len(snippet) + 200
                if total_chars + estimated_cost < MAX_PROMPT_CHARS:
                    file_contents.append(f"### {file_path}\n```\n{snippet}\n```")
                    total_chars += estimated_cost
                else:
                    break  # Stop when we hit budget limit
            except Exception:
                continue
        if file_contents:
            full_files_section = f"FULL FILE CONTENTS:\n{chr(10).join(file_contents)}\n\n"

    # Calculate remaining budget for diff and check if truncation needed
    diff_budget = max(1000, MAX_PROMPT_CHARS - len(guidelines_section) - len(full_files_section))
    diff_truncated = len(augmented_diff) > diff_budget
    local_tools_section = (
        ""
        if not is_agent_review_model  # must match the get_agent_response fallback gate
        else (
            "AVAILABLE TOOLS:\n"
            "- read_file: inspect bounded line ranges from repository files, including unchanged files\n"
            "- search_repo: find related definitions, dependencies, tests, config, or existing patterns across the checkout\n"
            "- list_files: locate repository files by glob\n"
            "- web_search: verify current public docs, package docs, release notes, issues, or vendor behavior when a "
            "review finding depends on external behavior\n"
            "- Do not quote large tool output. Use tools only to verify concise, actionable review findings.\n\n"
        )
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
        "- Issues in unchanged context lines\n\n"
        "LIMITED VISIBILITY - IMPORTANT:\n"
        "- Start from the diff, then use tools to inspect full files or related code when context affects a finding\n"
        "- Assume the author is knowledgeable about: new package versions, imports to functions defined elsewhere, dependencies, and codebase architecture unless tool evidence proves otherwise\n"
        "- Do NOT flag: version updates, new imports that appear unused in the diff, or references to code outside the diff\n"
        "- If unsure whether something is an error, assume the author knows what they're doing\n"
        "- If PROJECT GUIDELINES (CLAUDE.md/AGENTS.md) are provided, respect project-specific conventions and standards\n\n"
        f"{local_tools_section}"
        "QUALITY OVER QUANTITY:\n"
        "- Zero comments is valid for clean PRs - don't invent issues\n"
        "- Each comment must be actionable with clear reasoning\n"
        "- Combine related issues into one comment\n"
        f"- Hard cap: {MAX_REVIEW_COMMENTS} comments maximum\n\n"
        "SUGGESTIONS:\n"
        "- Provide 'suggestion' field with ready-to-merge code when you can confidently fix the issue\n"
        "- Suggestions must be complete, working code with NO comments, placeholders, or explanations\n"
        "- Single-line fixes only: provide 'suggestion' without 'start_line' to replace the line at 'line'\n"
        "- Match the exact indentation of the original code\n"
        "- Avoid triple backticks (```) in suggestions as they break Markdown formatting\n\n"
        "SUMMARY:\n"
        "- Brief overall assessment: what's good, what needs attention\n"
        "- If no issues found, acknowledge the PR is clean\n\n"
        "DIFF LINE FORMAT (how to read line numbers):\n"
        '  R  123 +code here      <- \'R\' means RIGHT (new file), number is 123, use {"line": 123, "side": "RIGHT"}\n'
        '  L   45 -code here      <- \'L\' means LEFT (old file), number is 45, use {"line": 45, "side": "LEFT"}\n'
        "         context         <- no prefix = unchanged context, don't comment on these\n"
        "- Extract the integer after R or L prefix (e.g., 'R  123' -> line 123, 'L   45' -> line 45)\n"
        "- Suggestions ONLY work on RIGHT (added) lines, never LEFT (removed) lines\n"
        "- ONLY use line numbers you see explicitly prefixed with R or L in the diff\n\n"
        "Return JSON: "
        '{"comments": [{"file": "exact/path", "line": N, "side": "RIGHT", "severity": "HIGH", "message": "..."}], "summary": "..."}\n\n'
        "JSON rules: exact paths (no ./), severity: CRITICAL|HIGH|MEDIUM|LOW|SUGGESTION\n"
        f"Files changed: {len(file_list)} ({', '.join(file_list[:30])}{'...' if len(file_list) > 30 else ''}), Lines: {lines_changed}\n"
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

        tools, tool_handlers = build_review_agent_tools()
        response = get_agent_response(
            messages,
            text_format={"format": {"type": "json_schema", "name": "pr_review", "strict": True, "schema": schema}},
            model=review_model,
            tools=tools,
            tool_handlers=tool_handlers,
            max_turns=MAX_AGENT_TURNS,
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
        return {"comments": [], "summary": summary}


def dismiss_previous_reviews(event: Action) -> int:
    """Dismiss previous bot reviews and delete inline comments, returns count for numbering."""
    if not (pr_number := event.pr.get("number")) or not (bot_username := event.get_username()):
        return 1

    review_count = 0
    reviews_base = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    reviews_url = f"{reviews_base}?per_page=100"
    if (response := event.get(reviews_url)).status_code == 200:
        for review in response.json():
            if review.get("user", {}).get("login") == bot_username and REVIEW_MARKER in (review.get("body") or ""):
                review_count += 1
                if review.get("state") in ["APPROVED", "CHANGES_REQUESTED"] and (review_id := review.get("id")):
                    event.put(f"{reviews_base}/{review_id}/dismissals", json={"message": "Superseded by new review"})

    # Delete previous inline comments
    comments_url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/comments?per_page=100"
    delete_base = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/comments"
    if (response := event.get(comments_url)).status_code == 200:
        for comment in response.json():
            if comment.get("user", {}).get("login") == bot_username and (comment_id := comment.get("id")):
                event.delete(
                    f"{delete_base}/{comment_id}",
                    expected_status=[200, 204, 404],
                )

    return review_count + 1


def get_local_head_sha() -> str | None:
    """Get the current HEAD SHA from local git repo."""
    import subprocess

    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Failed to get local HEAD SHA: {e}")
        return None


def post_review_summary(event: Action, review_data: dict, review_number: int) -> None:
    """Post overall review summary and inline comments as a single PR review."""
    if not (pr_number := event.pr.get("number")):
        return

    # Use local HEAD SHA to avoid "Line could not be resolved" errors when auto-format pushed new commits
    commit_sha = get_local_head_sha() or event.pr.get("head", {}).get("sha")
    if not commit_sha:
        return

    review_title = f"{REVIEW_MARKER} {review_number}" if review_number > 1 else REVIEW_MARKER
    comments = review_data.get("comments", [])
    summary = review_data.get("summary") or ""

    # Don't approve if error occurred, inline comments exist, or medium-or-higher severity issues
    has_error = not summary or ERROR_MARKER in summary
    has_inline_comments = review_data.get("comments_before_filtering", 0) > 0
    has_issues = any(c.get("severity") not in ["LOW", "SUGGESTION", None] for c in comments)
    event_type = "COMMENT" if (has_error or has_inline_comments or has_issues) else "APPROVE"

    body = f"{review_title}\n\n{ACTIONS_CREDIT}\n\n{summary[:3000]}\n\n"

    if comments:
        body += f"💬 Posted {len(comments)} inline comment{'s' if len(comments) != 1 else ''}\n"

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

    event.post(f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews", json=payload)


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
    review_number = dismiss_previous_reviews(event)

    diff = event.get_pr_diff()
    review = generate_pr_review(event.repository, diff, event.pr.get("title") or "", event.pr.get("body") or "", event)

    post_review_summary(event, review, review_number)
    print("PR review completed")


if __name__ == "__main__":
    main()
