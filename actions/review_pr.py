# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import re
from pathlib import Path

from .utils import (
    ACTIONS_CREDIT,
    GITHUB_API_URL,
    MAX_PROMPT_CHARS,
    Action,
    format_skipped_files_dropdown,
    get_response,
    remove_html_comments,
    sanitize_ai_text,
    should_skip_file,
)

REVIEW_MARKER = "## 🔍 PR Review"
ERROR_MARKER = "⚠️ Review generation encountered an error"
EMOJI_MAP = {"CRITICAL": "❗", "HIGH": "⚠️", "MEDIUM": "💡", "LOW": "📝", "SUGGESTION": "💭"}
MAX_CONTEXT_FILE_CHARS = 5000
MAX_REVIEW_COMMENTS = 8
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SUGGESTION": 4, None: 5}


def parse_diff_files(diff_text: str) -> tuple[dict, str]:
    """Parse diff and return file mapping with line numbers AND augmented diff with explicit line numbers.

    Structure: files[file]["RIGHT"][line] -> str (added line text) files[file]["LEFT"][line] -> str (removed line text)
    files[file]["_HUNK"]["RIGHT"][line] -> int (hunk id) files[file]["_HUNK"]["LEFT"][line] -> int (hunk id)
    """
    files, current_file, new_line, old_line = {}, None, 0, 0
    augmented_lines, hunk_id = [], -1

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            match = re.search(r" b/(.+)$", line)
            current_file = match.group(1) if match else None
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
    diff_truncated = len(augmented_diff) > MAX_PROMPT_CHARS
    lines_changed = sum(len(sides["RIGHT"]) + len(sides["LEFT"]) for sides in diff_files.values())

    # Fetch full file contents for better context if within token budget
    full_files_section = ""
    if event and len(file_list) <= 10:  # Reasonable file count limit
        file_contents, total_chars = [], len(augmented_diff)
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
                # Only include if within budget, include buffer for markdown noise
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
        "- You can only see the diff and partial file contents, not the full codebase\n"
        "- Assume the author is knowledgeable about: new package versions, imports to functions defined elsewhere, dependencies, and codebase architecture\n"
        "- Do NOT flag: version updates, new imports that appear unused in the diff, or references to code outside the diff\n"
        "- If unsure whether something is an error, assume the author knows what they're doing\n\n"
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
        "- Avoid triple backticks (```) in suggestions as they break markdown formatting\n\n"
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
                f"{full_files_section}"
                f"DIFF:\n{augmented_diff[:MAX_PROMPT_CHARS]}\n\n"
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

        response = get_response(
            messages,
            reasoning_effort="low",
            model="gpt-5.2-2025-12-11",
            text_format={"format": {"type": "json_schema", "name": "pr_review", "strict": True, "schema": schema}},
            tools=[
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": [
                            "ultralytics.com",
                            "github.com",
                            "stackoverflow.com",
                        ]
                    },
                }
            ],
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
                    print(f"Dropping start_line for {file_path}:{line_num} - suggestions must be single-line only")
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


def post_review_summary(event: Action, review_data: dict, review_number: int) -> None:
    """Post overall review summary and inline comments as a single PR review."""
    if not (pr_number := event.pr.get("number")) or not (commit_sha := event.pr.get("head", {}).get("sha")):
        return

    review_title = f"{REVIEW_MARKER} {review_number}" if review_number > 1 else REVIEW_MARKER
    comments = review_data.get("comments", [])
    summary = review_data.get("summary") or ""

    # Don't approve if error occurred, inline comments exist, or critical/high severity issues
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
