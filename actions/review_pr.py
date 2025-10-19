# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import re

from .utils import GITHUB_API_URL, Action, get_completion

REVIEW_KEYWORD = "@ultralytics/review"
REVIEW_MARKER = "🔍 PR Review"
EMOJI_MAP = {"CRITICAL": "❗", "HIGH": "⚠️", "MEDIUM": "💡", "LOW": "📝", "SUGGESTION": "💭"}


def parse_diff_files(diff_text: str) -> dict:
    """Parse diff to extract file paths, valid line numbers, and line content for comments."""
    files, current_file, current_line = {}, None, 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            match = re.search(r" b/(.+)$", line)
            current_file = match.group(1) if match else None
            current_line = 0
            if current_file:
                files[current_file] = {}
        elif line.startswith("@@") and current_file:
            match = re.search(r"@@.*\+(\d+)(?:,\d+)?", line)
            current_line = int(match.group(1)) if match else 0
        elif current_file and current_line > 0:
            if line.startswith("+") and not line.startswith("+++"):
                files[current_file][current_line] = line[1:]
                current_line += 1
            elif not line.startswith("-"):
                current_line += 1

    return files


def generate_pr_review(repository: str, diff_text: str, pr_title: str, pr_description: str) -> dict:
    """Generate comprehensive PR review with line-specific comments and overall assessment."""
    if not diff_text or "**ERROR" in diff_text:
        return {"comments": [], "summary": f"Unable to review: {diff_text if '**ERROR' in diff_text else 'diff empty'}"}

    diff_files = parse_diff_files(diff_text)
    if not diff_files:
        return {"comments": [], "summary": "No files with changes detected in diff"}

    file_list = list(diff_files.keys())
    limit = round(128000 * 3.3 * 0.4)
    diff_truncated = len(diff_text) > limit
    lines_changed = sum(len(lines) for lines in diff_files.values())

    valid_lines_text = "\n".join(
        f"  {file}: {sorted(list(lines.keys())[:20])}{' ...' if len(lines) > 20 else ''}"
        for file, lines in list(diff_files.items())[:10]
    ) + ("\n  ..." if len(diff_files) > 10 else "")

    priority_guidance = (
        "Prioritize the most critical/high-impact issues only"
        if lines_changed >= 100
        else "Prioritize commenting on different files/sections"
    )

    content = (
        "You are an expert code reviewer for Ultralytics. Provide detailed inline comments on specific code changes.\n\n"
        "Focus on: Code quality, style, best practices, bugs, edge cases, error handling, performance, security, documentation, test coverage\n\n"
        "FORMATTING: Use backticks for code, file names, branch names, function names, variable names, packages\n\n"
        "CRITICAL RULES:\n"
        f"1. Generate inline comments with recommended changes for clear bugs/security/syntax issues (up to 10)\n"
        "2. Each comment MUST reference a UNIQUE line number(s)\n"
        "3. If a line has multiple issues, combine ALL issues into ONE comment for that line\n"
        "4. Never create separate comments for the same line number\n"
        f"5. {priority_guidance}\n\n"
        "CODE SUGGESTIONS:\n"
        "- ONLY provide 'suggestion' field when you have HIGH CERTAINTY the code is problematic AND sufficient context for a confident fix\n"
        "- If uncertain about the correct fix, omit 'suggestion' field and explain the concern in 'message' only\n"
        "- Suggestions must be ready-to-merge code with NO comments, placeholders, or explanations\n"
        "- When providing suggestions, ensure they are complete, correct, and maintain existing indentation\n"
        "- It's better to flag an issue without a suggestion than provide a wrong or uncertain fix\n\n"
        "Return JSON: "
        '{"comments": [{"file": "exact/path", "line": N, "severity": "HIGH", "message": "...", "suggestion": "..."}], "summary": "..."}\n\n'
        "Rules:\n"
        "- Only comment on NEW lines (starting with + in diff)\n"
        "- Use exact file paths from diff (no ./ prefix)\n"
        "- Line numbers must match NEW file line numbers from @@ hunks\n"
        "- When '- old' then '+ new', new line keeps SAME line number\n"
        "- Severity: CRITICAL, HIGH, MEDIUM, LOW, SUGGESTION\n"
        f"- Files changed: {len(file_list)} ({', '.join(file_list[:10])}{'...' if len(file_list) > 10 else ''})\n"
        f"- Total changed lines: {lines_changed}\n"
        f"- Diff {'truncated' if diff_truncated else 'complete'}: {len(diff_text[:limit])} chars{f' of {len(diff_text)}' if diff_truncated else ''}\n\n"
        f"VALID LINE NUMBERS (use ONLY these):\n{valid_lines_text}"
    )

    messages = [
        {"role": "system", "content": content},
        {
            "role": "user",
            "content": f"Review PR '{repository}':\nTitle: {pr_title}\nDescription: {pr_description[:500]}\n\nDiff:\n{diff_text[:limit]}",
        },
    ]

    try:
        response = get_completion(messages, reasoning_effort="medium")
        print("\n" + "=" * 80 + f"\nFULL AI RESPONSE:\n{response}\n" + "=" * 80 + "\n")

        json_str = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        review_data = json.loads(json_str.group(1) if json_str else response)

        print(f"AI generated {len(review_data.get('comments', []))} comments")

        # Validate, filter, and deduplicate comments
        unique_comments = {}
        for c in review_data.get("comments", []):
            file_path, line_num = c.get("file"), c.get("line", 0)
            if file_path in diff_files and line_num in diff_files[file_path]:
                key = f"{file_path}:{line_num}"
                if key not in unique_comments:
                    unique_comments[key] = c
                else:
                    print(f"⚠️  AI duplicate for {key}: {c.get('severity')} - {c.get('message')[:60]}...")
            else:
                print(f"Filtered out {file_path}:{line_num} (available: {list(diff_files.get(file_path, {}))[:10]}...)")

        review_data.update(
            {"comments": list(unique_comments.values()), "diff_files": diff_files, "diff_truncated": diff_truncated}
        )
        print(f"Valid comments after filtering: {len(review_data['comments'])}")
        return review_data

    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}\nAttempted: {json_str[:500] if 'json_str' in locals() else response[:500]}...")
        return {"comments": [], "summary": "Review generation encountered a JSON parsing error"}
    except Exception as e:
        print(f"Review generation failed: {e}")
        import traceback

        traceback.print_exc()
        return {"comments": [], "summary": "Review generation encountered an error"}


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


def post_review_comments(event: Action, review_data: dict) -> None:
    """Post inline review comments on specific lines of the PR."""
    if not (pr_number := event.pr.get("number")) or not (commit_sha := event.pr.get("head", {}).get("sha")):
        return

    url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/comments"
    diff_files = review_data.get("diff_files", {})

    for comment in review_data.get("comments", [])[:50]:
        if not (file_path := comment.get("file")) or not (line := comment.get("line", 0)):
            continue

        severity = comment.get("severity", "SUGGESTION")
        body = f"{EMOJI_MAP.get(severity, '💭')} **{severity}**: {comment.get('message', '')}"

        if suggestion := comment.get("suggestion"):
            original_line = diff_files.get(file_path, {}).get(line, "")
            indent = len(original_line) - len(original_line.lstrip())
            indented = "\n".join(" " * indent + l if l.strip() else l for l in suggestion.split("\n"))
            body += f"\n\n**Suggested change:**\n```suggestion\n{indented}\n```"

        event.post(url, json={"body": body, "commit_id": commit_sha, "path": file_path, "line": line, "side": "RIGHT"})


def post_review_summary(event: Action, review_data: dict, review_number: int) -> None:
    """Post overall review summary as a PR review."""
    if not (pr_number := event.pr.get("number")) or not (commit_sha := event.pr.get("head", {}).get("sha")):
        return

    review_title = f"{REVIEW_MARKER} {review_number}" if review_number > 1 else REVIEW_MARKER
    comments = review_data.get("comments", [])
    max_severity = max((c.get("severity") for c in comments), default="SUGGESTION") if comments else None
    event_type = "APPROVE" if not comments or max_severity in ["LOW", "SUGGESTION"] else "REQUEST_CHANGES"

    body = (
        f"## {review_title}\n\n"
        "<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)</sub>\n\n"
        f"{review_data.get('summary', 'Review completed')}\n\n"
    )

    if comments:
        shown = min(len(comments), 50)
        body += f"💬 Posted {shown} inline comment{'s' if shown != 1 else ''}{' (50 shown, more available)' if len(comments) > 50 else ''}\n"

    if review_data.get("diff_truncated"):
        body += "\n⚠️ **Large PR**: Review focused on critical issues. Some details may not be covered.\n"

    event.post(
        f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}/reviews",
        json={"commit_id": commit_sha, "body": body, "event": event_type},
    )


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
        if event.event_data.get("requested_reviewer", {}).get("login") != event.get_username():
            return
        print(f"Review requested from {event.get_username()}")

    if not event.pr or event.pr.get("state") != "open":
        print(f"Skipping: PR state is {event.pr.get('state') if event.pr else 'None'}")
        return

    print(f"Starting PR review for #{event.pr['number']}")
    review_number = dismiss_previous_reviews(event)

    diff = event.get_pr_diff()
    review = generate_pr_review(event.repository, diff, event.pr.get("title", ""), event.pr.get("body", ""))

    post_review_summary(event, review, review_number)
    print(f"Posting {len(review.get('comments', []))} inline comments")
    post_review_comments(event, review)

    if event.event_name == "issue_comment":
        event.toggle_eyes_reaction(False)

    print("PR review completed")


if __name__ == "__main__":
    main()
