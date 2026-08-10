# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

from .utils import (
    ACTIONS_CREDIT,
    GITHUB_API_URL,
    Action,
    format_skipped_files_dropdown,
    get_pr_summary_prompt,
    get_response,
    remove_html_comments,
)

SUMMARY_MARKER = "## 🛠️ PR Summary"


def generate_merge_message(pr_summary, pr_credit, pr_url):
    """Generate a personalized thank-you message for a merged pull request."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are an Ultralytics AI assistant. Your response is posted verbatim as a GitHub comment on a "
                "merged PR. Return only the final comment body with no preamble, sign-off, or horizontal rule."
            ),
        },
        {
            "role": "user",
            "content": f"""Thank {pr_credit} for the merged PR {pr_url} using the verified context below.

{pr_summary}

- Start with an enthusiastic note that the PR was merged.
- Include exactly one short, accurately attributed inspirational quote in a Markdown blockquote.
- Connect the quote to the concrete impact described in the PR summary without inventing results or benefits.
- Keep the complete comment concise and meaningful.""",
        },
    ]
    return get_response(messages)


def generate_pr_summary(repository, diff_text, title="", description=""):
    """Generates a concise, professional summary of a PR using the OpenAI or Anthropic API."""
    prompt, is_large, skipped_files = get_pr_summary_prompt(repository, diff_text, title, description)

    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant skilled in software development and technical communication. Your task is to summarize GitHub PRs from Ultralytics in a way that is accurate, concise, and understandable to both expert developers and non-expert users. Focus on highlighting the key changes and their impact in simple, concise terms.",
        },
        {"role": "user", "content": prompt},
    ]
    reply = get_response(messages, temperature=1.0)
    if is_large:
        reply = "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + reply

    # Add skipped files dropdown if any files were filtered
    skipped_dropdown = format_skipped_files_dropdown(skipped_files)

    return f"{SUMMARY_MARKER}\n\n{ACTIONS_CREDIT}\n\n{reply}{skipped_dropdown}"


def label_fixed_issues(event, pr_summary):
    """Labels issues closed by PR when merged, notifies users, and returns PR contributors."""
    pr_credit, data = event.get_pr_contributors()
    if not data:
        return None

    credit = f" by {pr_credit}" if pr_credit else ""
    synopsis = ""
    if "### 🌟 Summary" in pr_summary and "### 📊 Key Changes" in pr_summary:
        synopsis = pr_summary.split("### 🌟 Summary", 1)[1].split("### 📊 Key Changes", 1)[0].strip()
    details = f"\n\n{synopsis}" if synopsis else ""
    comment = (
        f"A potential fix is now available in the [merged pull request]({data['url']}){credit}.{details}\n\n"
        "Please test the merged change using "
        "this repository's documented workflow. If the issue persists, "
        "share the updated behavior and any new diagnostic details. Thank you for reporting it! 🙏"
    )

    for issue in data["closingIssuesReferences"]["nodes"]:
        number = issue["number"]
        event.post(f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/labels", json={"labels": ["fixed"]})
        event.post(f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/comments", json={"body": comment})

    return pr_credit


def main(*args, **kwargs):
    """Summarize a pull request and update its description with a summary."""
    event = Action(*args, **kwargs)
    action = event.event_data.get("action")
    if action == "opened":
        print("Skipping PR open - handled by first_interaction.py with unified API call")
        return
    if event.should_skip_llm():
        return

    print(f"Retrieving diff for PR {event.pr['number']}")
    diff = event.get_pr_diff()

    # Generate PR summary
    print("Generating PR summary...")
    description = (event.pr.get("body") or "").split(SUMMARY_MARKER)[0]
    summary = generate_pr_summary(
        event.repository, diff, event.pr.get("title") or "", remove_html_comments(description)
    )

    # Update PR description
    print("Updating PR description...")
    event.update_pr_description(event.pr["number"], summary, fallback_description=event.pr.get("body") or "")

    if event.pr.get("merged"):
        print("PR is merged, labeling fixed issues...")
        pr_credit = label_fixed_issues(event, summary)
        if any(label["name"] == "TODO" for label in event.pr.get("labels", [])):
            print("Removing TODO label from PR...")
            event.remove_labels(event.pr["number"], labels=("TODO",))
        if pr_credit:
            print("Posting PR author thank you message...")
            event.add_comment(
                event.pr["number"],
                None,
                generate_merge_message(summary, pr_credit, event.pr["html_url"]),
                "pull request",
            )


if __name__ == "__main__":
    main()
