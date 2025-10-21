# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import re

from .utils import GITHUB_API_URL, MAX_PROMPT_CHARS, Action, get_completion, remove_html_comments

REVIEW_MARKER = "🔍 PR Review"
ERROR_MARKER = "⚠️ Review generation encountered an error"
EMOJI_MAP = {"CRITICAL": "❗", "HIGH": "⚠️", "MEDIUM": "💡", "LOW": "📝", "SUGGESTION": "💭"}
SKIP_PATTERNS = [
    r"\.lock$",  # Lock files
    r"-lock\.(json|yaml|yml)$",
    r"\.min\.(js|css)$",  # Minified
    r"\.bundle\.(js|css)$",
    r"(^|/)dist/",  # Generated/vendored directories
    r"(^|/)build/",
    r"(^|/)vendor/",
    r"(^|/)node_modules/",
    r"\.pb\.py$",  # Proto generated
    r"_pb2\.py$",
    r"_pb2_grpc\.py$",
    r"^package-lock\.json$",  # Package locks
    r"^yarn\.lock$",
    r"^poetry\.lock$",
    r"^Pipfile\.lock$",
    r"\.(svg|png|jpe?g|gif)$",  # Images
]


def parse_diff_files(diff_text: str) -> dict:
    """Parse diff to extract file paths, valid line numbers, and line content for comments (both sides)."""
    files, current_file, new_line, old_line = {}, None, 0, 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            match = re.search(r" b/(.+)$", line)
            current_file = match.group(1) if match else None
            new_line, old_line = 0, 0
            if current_file:
                files[current_file] = {"RIGHT": {}, "LEFT": {}}
        elif line.startswith("@@") and current_file:
            # Extract both old and new line numbers
            match = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?", line)
            if match:
                old_line, new_line = int(match.group(1)), int(match.group(2))
        elif current_file and (new_line > 0 or old_line > 0):
            if line.startswith("+") and not line.startswith("+++"):
                files[current_file]["RIGHT"][new_line] = line[1:]  # Added line (right/new side)
                new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                files[current_file]["LEFT"][old_line] = line[1:]  # Removed line (left/old side)
                old_line += 1
            elif not line.startswith("\\"):  # Context line (ignore "No newline" markers)
                new_line += 1
                old_line += 1

    return files


def generate_pr_review(repository: str, diff_text: str, pr_title: str, pr_description: str) -> dict:
    """Generate comprehensive PR review with line-specific comments and overall assessment."""
    if not diff_text:
        return {"comments": [], "summary": "No changes detected in diff"}

    diff_files = parse_diff_files(diff_text)
    if not diff_files:
        return {"comments": [], "summary": "No files with changes detected in diff"}

    # Filter out generated/vendored files
    filtered_files = {
        path: sides
        for path, sides in diff_files.items()
        if not any(re.search(pattern, path) for pattern in SKIP_PATTERNS)
    }
    skipped_count = len(diff_files) - len(filtered_files)
    diff_files = filtered_files

    if not diff_files:
        return {"comments": [], "summary": f"All {skipped_count} changed files are generated/vendored (skipped review)"}

    file_list = list(diff_files.keys())
    diff_truncated = len(diff_text) > MAX_PROMPT_CHARS
    lines_changed = sum(len(sides["RIGHT"]) + len(sides["LEFT"]) for sides in diff_files.values())

    content = (
        "You are an expert code reviewer for Ultralytics. Provide detailed inline comments on specific code changes.\n\n"
        "Focus on: Bugs, security, performance, best practices, edge cases, error handling\n\n"
        "FORMATTING: Use backticks for code: `x=3`, `file.py`, `function()`\n\n"
        "CRITICAL RULES:\n"
        "1. Quality over quantity - zero comments is fine for clean code, only flag truly important issues\n"
        "2. Combine issues that are directly related to the same problem\n"
        "3. Use 'start_line' and 'line' to highlight multi-line ranges when issues span multiple lines\n"
        "4. Prioritize: CRITICAL bugs/security > HIGH impact > code quality improvements\n"
        "5. Keep comments concise and friendly - avoid jargon\n"
        "6. Skip routine changes: imports, version updates, standard refactoring\n\n"
        "SUMMARY:\n"
        "- Brief and actionable - what needs fixing, not where (locations shown in inline comments)\n\n"
        "SUGGESTIONS:\n"
        "- ONLY provide 'suggestion' field when you have high certainty the code is problematic AND sufficient context for a confident fix\n"
        "- If uncertain about the correct fix, omit 'suggestion' field and explain the concern in 'message' only\n"
        "- Suggestions must be ready-to-merge code with NO comments, placeholders, or explanations\n"
        "- Suggestions replace ONLY the single line at 'line' - for multi-line fixes, describe the change in 'message' instead\n"
        "- Do NOT provide 'start_line' when including a 'suggestion' - suggestions are always single-line only\n"
        "- Suggestion content must match the exact indentation of the original line\n"
        "- Avoid triple backticks (```) in suggestions as they break markdown formatting\n"
        "- It's better to flag an issue without a suggestion than provide a wrong or uncertain fix\n\n"
        "LINE NUMBERS:\n"
        "- You MUST extract line numbers directly from the @@ hunk headers in the diff below\n"
        "- RIGHT (added +): Find @@ lines, use numbers after +N (e.g., @@ -10,5 +20,7 @@ means RIGHT starts at line 20)\n"
        "- LEFT (removed -): Find @@ lines, use numbers after -N (e.g., @@ -10,5 +20,7 @@ means LEFT starts at line 10)\n"
        "- Count forward from hunk start: + lines increment RIGHT, - lines increment LEFT, context lines increment both\n"
        "- CRITICAL: Using line numbers not in the diff will cause your comment to be rejected\n"
        "- Suggestions only work on RIGHT (added) lines, never on LEFT (removed) lines\n\n"
        "Return JSON: "
        '{"comments": [{"file": "exact/path", "line": N, "side": "RIGHT", "severity": "HIGH", "message": "..."}], "summary": "..."}\n\n'
        "Rules:\n"
        "- Verify line numbers from @@ hunks: +N for RIGHT (added), -N for LEFT (removed)\n"
        "- Exact paths (no ./), 'side' field defaults to RIGHT if omitted\n"
        "- Severity: CRITICAL, HIGH, MEDIUM, LOW, SUGGESTION\n"
        f"- Files changed: {len(file_list)} ({', '.join(file_list[:10])}{'...' if len(file_list) > 10 else ''})\n"
        f"- Lines changed: {lines_changed}\n"
    )

    messages = [
        {"role": "system", "content": content},
        {
            "role": "user",
            "content": (
                f"Review this PR in https://github.com/{repository}:\n"
                f"Title: {pr_title}\n"
                f"Description: {remove_html_comments(pr_description or '')[:1000]}\n\n"
                f"Diff:\n{diff_text[:MAX_PROMPT_CHARS]}\n\n"
                "Now review this diff according to the rules above. Return JSON with comments array and summary."
            ),
        },
    ]

    try:
        response = get_completion(messages, reasoning_effort="medium", model="gpt-5-codex")

        json_str = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        review_data = json.loads(json_str.group(1) if json_str else response)
        print(json.dumps(review_data, indent=2))
        print(f"AI generated {len(review_data.get('comments', []))} comments")

        # Validate, filter, and deduplicate comments
        unique_comments = {}
        for c in review_data.get("comments", []):
            file_path, line_num = c.get("file"), c.get("line", 0)
            start_line = c.get("start_line")
            side = (c.get("side") or "RIGHT").upper()  # Default to RIGHT (added lines)

            # Validate line numbers are in diff (check appropriate side)
            if file_path not in diff_files:
                print(f"Filtered out {file_path}:{line_num} (file not in diff)")
                continue
            if line_num not in diff_files[file_path].get(side, {}):
                # Try other side if not found
                other_side = "LEFT" if side == "RIGHT" else "RIGHT"
                if line_num in diff_files[file_path].get(other_side, {}):
                    print(f"Switching {file_path}:{line_num} from {side} to {other_side}")
                    c["side"] = other_side
                    side = other_side
                    # GitHub rejects suggestions on removed lines
                    if side == "LEFT" and c.get("suggestion"):
                        print(f"Dropping suggestion for {file_path}:{line_num} - LEFT side doesn't support suggestions")
                        c.pop("suggestion", None)
                else:
                    available = {s: list(diff_files[file_path][s].keys())[:10] for s in ["RIGHT", "LEFT"]}
                    print(f"Filtered out {file_path}:{line_num} (available: {available})")
                    continue

            # Validate start_line if provided - drop start_line for suggestions (single-line only)
            if start_line:
                if c.get("suggestion"):
                    print(f"Dropping start_line for {file_path}:{line_num} - suggestions must be single-line only")
                    c.pop("start_line", None)
                elif start_line >= line_num:
                    print(f"Invalid start_line {start_line} >= line {line_num} for {file_path}, dropping start_line")
                    c.pop("start_line", None)
                elif start_line not in diff_files[file_path].get(side, {}):
                    print(f"start_line {start_line} not in diff for {file_path}, dropping start_line")
                    c.pop("start_line", None)

            # Deduplicate by line number and side
            key = f"{file_path}:{side}:{line_num}"
            if key not in unique_comments:
                unique_comments[key] = c
            else:
                print(f"⚠️  AI duplicate for {key}: {c.get('severity')} - {(c.get('message') or '')[:60]}...")

        review_data.update(
            {
                "comments": list(unique_comments.values()),
                "diff_files": diff_files,
                "diff_truncated": diff_truncated,
                "skipped_files": skipped_count,
            }
        )
        print(f"Valid comments after filtering: {len(review_data['comments'])}")
        return review_data

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
    reviews_url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    if (response := event.get(reviews_url)).status_code == 200:
        for review in response.json():
            if review.get("user", {}).get("login") == bot_username and REVIEW_MARKER in (review.get("body") or ""):
                review_count += 1
                if review.get("state") in ["APPROVED", "CHANGES_REQUESTED"] and (review_id := review.get("id")):
                    event.put(f"{reviews_url}/{review_id}/dismissals", json={"message": "Superseded by new review"})

    # Delete previous inline comments
    comments_url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/comments"
    if (response := event.get(comments_url)).status_code == 200:
        for comment in response.json():
            if comment.get("user", {}).get("login") == bot_username and (comment_id := comment.get("id")):
                event.delete(
                    f"{GITHUB_API_URL}/repos/{event.repository}/pulls/comments/{comment_id}",
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

    # Don't approve if error occurred or if there are critical/high severity issues
    has_error = not summary or ERROR_MARKER in summary
    has_issues = any(c.get("severity") not in ["LOW", "SUGGESTION", None] for c in comments)
    requests_changes = any(
        phrase in summary.lower()
        for phrase in [
            "please",
            "should",
            "must",
            "raise",
            "needs",
            "before merging",
            "fix",
            "error",
            "issue",
            "problem",
            "warning",
            "concern",
        ]
    )
    event_type = "COMMENT" if (has_error or has_issues or requests_changes) else "APPROVE"

    body = (
        f"## {review_title}\n\n"
        "<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)</sub>\n\n"
        f"{review_data.get('summary', 'Review completed')[:1000]}\n\n"  # Clip summary length
    )

    if comments:
        shown = min(len(comments), 10)
        body += f"💬 Posted {shown} inline comment{'s' if shown != 1 else ''}\n"

    if review_data.get("diff_truncated"):
        body += "\n⚠️ **Large PR**: Review focused on critical issues. Some details may not be covered.\n"

    if skipped := review_data.get("skipped_files"):
        body += f"\n📋 **Skipped {skipped} file{'s' if skipped != 1 else ''}** (lock files, minified, images, etc.)\n"

    # Build inline comments for the review
    review_comments = []
    for comment in comments[:10]:  # Limit inline comments
        if not (file_path := comment.get("file")) or not (line := comment.get("line", 0)):
            continue

        severity = comment.get("severity") or "SUGGESTION"
        comment_body = f"{EMOJI_MAP.get(severity, '💭')} **{severity}**: {(comment.get('message') or '')[:1000]}"

        # Get side (LEFT for removed lines, RIGHT for added lines)
        side = comment.get("side", "RIGHT")

        if suggestion := comment.get("suggestion"):
            suggestion = suggestion[:1000]  # Clip suggestion length
            if "```" not in suggestion:
                # Extract original line indentation and apply to suggestion
                if original_line := review_data.get("diff_files", {}).get(file_path, {}).get(side, {}).get(line):
                    indent = len(original_line) - len(original_line.lstrip())
                    suggestion = " " * indent + suggestion.strip()
                comment_body += f"\n\n**Suggested change:**\n```suggestion\n{suggestion}\n```"

        # Build comment with optional start_line for multi-line context
        review_comment = {"path": file_path, "line": line, "body": comment_body, "side": side}
        if start_line := comment.get("start_line"):
            if start_line < line:
                review_comment["start_line"] = start_line
                review_comment["start_side"] = side
                print(f"Multi-line comment: {file_path}:{start_line}-{line} ({side})")

        review_comments.append(review_comment)

    # Submit review with inline comments
    payload = {"commit_id": commit_sha, "body": body, "event": event_type}
    if review_comments:
        payload["comments"] = review_comments
        print(f"Posting review with {len(review_comments)} inline comments")

    event.post(
        f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews",
        json=payload,
    )


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
    review = generate_pr_review(event.repository, diff, event.pr.get("title") or "", event.pr.get("body") or "")

    post_review_summary(event, review, review_number)
    print("PR review completed")


if __name__ == "__main__":
    main()
