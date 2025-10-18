# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import re

from .utils import GITHUB_API_URL, Action, get_completion

REVIEW_KEYWORD = "@ultralytics/review"
REVIEW_MARKER = "🔍 PR Review"


def parse_diff_files(diff_text: str) -> dict:
    """Parse diff to extract file paths, valid line numbers, and line content for comments."""
    files = {}
    current_file = None
    current_line = 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            match = re.search(r" b/(.+)$", line)
            current_file = match.group(1) if match else None
            current_line = 0
            if current_file:
                files[current_file] = {}
                print(f"Parsing file: {current_file}")
        elif line.startswith("@@") and current_file:
            match = re.search(r"@@.*\+(\d+)(?:,\d+)?", line)
            if match:
                current_line = int(match.group(1))
                print(f"  Hunk starts at line {current_line}: {line[:80]}")
            else:
                current_line = 0
        elif current_file and current_line > 0:
            if line.startswith("+") and not line.startswith("+++"):
                files[current_file][current_line] = line[1:]  # Store line content without '+' prefix
                print(f"  Added line {current_line}: {line[:80]}")
                current_line += 1
            elif not line.startswith("-"):
                current_line += 1

    for f, lines in files.items():
        print(f"File {f}: {len(lines)} changed lines")
    return files


def generate_pr_review(repository: str, diff_text: str, pr_title: str, pr_description: str) -> dict:
    """Generate comprehensive PR review with line-specific comments and overall assessment."""
    if not diff_text or "**ERROR" in diff_text:
        return {
            "comments": [],
            "summary": f"Unable to review: {diff_text if '**ERROR' in diff_text else 'diff empty'}",
            "approval": "COMMENT",
        }

    diff_files = parse_diff_files(diff_text)
    if not diff_files:
        return {"comments": [], "summary": "No files with changes detected in diff", "approval": "COMMENT"}

    file_list = list(diff_files.keys())
    _ratio, limit = 3.3, round(128000 * 3.3 * 0.4)
    diff_truncated = len(diff_text) > limit
    lines_changed = sum(len(lines) for lines in diff_files.values())

    # Build valid line numbers list for prompt
    valid_lines_text = "\n".join(
        f"  {file}: {sorted(list(lines.keys())[:20])}{' ...' if len(lines) > 20 else ''}"
        for file, lines in list(diff_files.items())[:10]
    )
    if len(diff_files) > 10:
        valid_lines_text += "\n  ..."

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert code reviewer for Ultralytics. Provide detailed inline comments on specific code changes.\n\n"
                "Focus on:\n"
                "- Code quality, style, best practices\n"
                "- Bugs, edge cases, error handling\n"
                "- Performance and security\n"
                "- Documentation and test coverage\n\n"
                "FORMATTING RULES:\n"
                "- Use backticks for: code, file names, branch names, function names, variable names, packages\n"
                "- Example: \"Use `main` instead of `review-pr-1` branch\"\n"
                "- Example: \"The `uses:` field should pin to a commit SHA\"\n"
                "- Keep messages clear and professional\n\n"
                "CRITICAL RULES:\n"
                f"1. Generate {3 if lines_changed < 100 else 'up to 10'} inline comments for DIFFERENT lines of code\n"
                "2. Each comment MUST reference a UNIQUE line number\n"
                "3. If a line has multiple issues, combine ALL issues into ONE comment for that line\n"
                "4. Never create separate comments for the same line number\n"
                f"5. {'Prioritize the most critical/high-impact issues only' if lines_changed >= 100 else 'Prioritize commenting on different files/sections rather than multiple aspects of one line'}\n\n"
                "Return JSON with this exact structure:\n"
                '{"comments": [{"file": "exact/path/from/diff", "line": N, "severity": "HIGH", "message": "...", "suggestion": "..."}], '
                '"summary": "Overall assessment", "approval": "APPROVE|REQUEST_CHANGES|COMMENT"}\n\n'
                "Rules:\n"
                "- Only comment on NEW lines (those starting with + in the diff)\n"
                "- Use exact file paths from the diff (no ./ prefix)\n"
                "- Line numbers must match the NEW file line numbers from @@ hunks\n"
                "- When you see '- old' then '+ new', the new line keeps the SAME line number as old\n"
                "- Severity: CRITICAL, HIGH, MEDIUM, LOW, SUGGESTION\n\n"
                "CRITICAL: Code suggestions must be ready-to-merge with NO comments:\n"
                "- 'suggestion' field: ONLY exact replacement code, no comments, no explanations, no alternatives\n"
                "- 'message' field: put explanation, rationale, and context here\n"
                "- Good suggestion: 'uses: ultralytics/actions@abc123def456'\n"
                "- Bad suggestion: 'uses: ultralytics/actions@<commit-sha> # explanation here'\n"
                "- Bad suggestion: Multiple options or lines with comments\n\n"
                f"- Files changed: {len(file_list)} ({', '.join(file_list[:10])}{'...' if len(file_list) > 10 else ''})\n"
                f"- Total changed lines: {lines_changed}\n"
                f"- Diff {'truncated' if diff_truncated else 'complete'}: {len(diff_text[:limit])} chars{f' of {len(diff_text)}' if diff_truncated else ''}\n\n"
                "VALID LINE NUMBERS (use ONLY these):\n"
                f"{valid_lines_text}"
            ),
        },
        {
            "role": "user",
            "content": f"Review PR '{repository}':\nTitle: {pr_title}\nDescription: {pr_description[:500]}\n\nDiff:\n{diff_text[:limit]}",
        },
    ]

    try:
        response = get_completion(messages, reasoning_effort="medium")
        print("\n" + "=" * 80)
        print("FULL AI RESPONSE:")
        print(response)
        print("=" * 80 + "\n")

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response
        review_data = json.loads(json_str)

        print(f"AI generated {len(review_data.get('comments', []))} comments")

        # Validate and filter comments
        valid_comments = []
        for c in review_data.get("comments", []):
            file_path, line_num = c.get("file"), c.get("line", 0)
            if file_path in diff_files and line_num in diff_files[file_path]:
                valid_comments.append(c)
            else:
                print(
                    f"Filtered out comment: {file_path}:{line_num} (available lines: {list(diff_files.get(file_path, {}))[:10]}...)"
                )

        # Deduplicate by (file, line) - keep first, log all duplicates
        unique_comments = {}
        for c in valid_comments:
            key = f"{c.get('file')}:{c.get('line')}"
            if key not in unique_comments:
                unique_comments[key] = c
            else:
                print(f"⚠️  AI duplicate for {key}: {c.get('severity')} - {c.get('message')[:60]}...")

        valid_comments = list(unique_comments.values())
        print(f"Valid comments after filtering and deduplication: {len(valid_comments)}")
        review_data["comments"] = valid_comments
        review_data["diff_files"] = diff_files
        review_data["diff_truncated"] = diff_truncated
        return review_data

    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        print(f"Attempted to parse: {json_str[:500]}...")
        return {"comments": [], "summary": "Review generation encountered a JSON parsing error", "approval": "COMMENT"}
    except Exception as e:
        print(f"Review generation failed: {e}")
        import traceback

        traceback.print_exc()
        return {"comments": [], "summary": "Review generation encountered an error", "approval": "COMMENT"}


def dismiss_previous_reviews(event: Action) -> None:
    """Dismiss previous bot reviews to avoid clutter."""
    if not (pr_number := event.pr.get("number")):
        return

    url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    response = event.get(url)

    if response.status_code != 200 or not (bot_username := event.get_username()):
        return

    for review in response.json():
        if review.get("user", {}).get("login") == bot_username and REVIEW_MARKER in (review.get("body") or ""):
            state = review.get("state")
            if state in ["APPROVED", "CHANGES_REQUESTED"] and (review_id := review.get("id")):
                event.put(f"{url}/{review_id}/dismissals", json={"message": "Superseded by new review"})


def post_review_comments(event: Action, review_data: dict) -> None:
    """Post inline review comments on specific lines of the PR."""
    if not (pr_number := event.pr.get("number")) or not (commit_sha := event.pr.get("head", {}).get("sha")):
        return

    emoji_map = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "💡", "LOW": "📝", "SUGGESTION": "💭"}
    url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/comments"
    diff_files = review_data.get("diff_files", {})

    for comment in review_data.get("comments", [])[:50]:
        if not (file_path := comment.get("file")) or not (line := comment.get("line", 0)):
            continue

        severity = comment.get("severity", "SUGGESTION")
        body = f"{emoji_map.get(severity, '💭')} **{severity}**: {comment.get('message', '')}"

        if suggestion := comment.get("suggestion"):
            # Extract indentation from original line and apply to suggestion
            original_line = diff_files.get(file_path, {}).get(line, "")
            indent = len(original_line) - len(original_line.lstrip())
            indented_suggestion = "\n".join(" " * indent + l if l.strip() else l for l in suggestion.split("\n"))
            body += f"\n\n**Suggested change:**\n```suggestion\n{indented_suggestion}\n```"

        event.post(url, json={"body": body, "commit_id": commit_sha, "path": file_path, "line": line, "side": "RIGHT"})


def post_review_summary(event: Action, review_data: dict) -> None:
    """Post overall review summary as a PR review."""
    if not (pr_number := event.pr.get("number")) or not (commit_sha := event.pr.get("head", {}).get("sha")):
        return

    comment_count = len(review_data.get("comments", []))
    event_map = {"APPROVE": "APPROVE", "REQUEST_CHANGES": "REQUEST_CHANGES", "COMMENT": "COMMENT"}
    event_type = event_map.get(review_data.get("approval", "COMMENT"), "COMMENT")
    diff_truncated = review_data.get("diff_truncated", False)

    body = (
        f"## {REVIEW_MARKER}\n\n"
        "<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)</sub>\n\n"
        f"{review_data.get('summary', 'Review completed')}\n\n"
    )

    if comment_count > 0:
        shown = min(comment_count, 50)
        body += f"💬 Posted {shown} inline comment{'s' if shown != 1 else ''}{' (50 shown, more available)' if comment_count > 50 else ''}\n"

    if diff_truncated:
        body += "\n⚠️ **Large PR**: Review focused on critical issues. Some details may not be covered.\n"

    url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews"
    event.post(url, json={"commit_id": commit_sha, "body": body, "event": event_type})


def main(*args, **kwargs):
    """Main entry point for PR review action."""
    event = Action(*args, **kwargs)

    # Handle comment-triggered reviews
    if event.event_name == "issue_comment":
        comment_body = event.event_data.get("comment", {}).get("body", "")
        username = event.event_data.get("comment", {}).get("user", {}).get("login", "")

        if REVIEW_KEYWORD not in comment_body or not event.is_org_member(username):
            return

        event.toggle_eyes_reaction(True)
        event.pr = event.get_repo_data(f"pulls/{event.event_data['issue']['number']}")

    # Handle review requests
    elif event.event_name == "pull_request" and event.event_data.get("action") == "review_requested":
        requested_reviewer = event.event_data.get("requested_reviewer", {}).get("login")
        bot_username = event.get_username()
        if requested_reviewer != bot_username:
            return
        print(f"Review requested from {bot_username}")

    # Validate PR state
    if not event.pr or event.pr.get("state") != "open":
        print(f"Skipping: PR state is {event.pr.get('state') if event.pr else 'None'}")
        return

    print(f"Starting PR review for #{event.pr['number']}")

    dismiss_previous_reviews(event)

    diff = event.get_pr_diff()
    review = generate_pr_review(event.repository, diff, event.pr.get("title", ""), event.pr.get("body", ""))

    post_review_summary(event, review)
    print(f"Posting {len(review.get('comments', []))} inline comments")
    post_review_comments(event, review)

    if event.event_name == "issue_comment":
        event.toggle_eyes_reaction(False)

    print("PR review completed")


if __name__ == "__main__":
    main()
