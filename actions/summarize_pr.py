# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

from .utils import (
    ACTIONS_CREDIT,
    GITHUB_API_URL,
    Action,
    format_skipped_files_dropdown,
    get_pr_summary_prompt,
    get_response,
)

SUMMARY_MARKER = "## 🛠️ PR Summary"


def generate_merge_message(pr_summary, pr_credit, pr_url):
    """Generates a motivating thank-you message for merged PR contributors."""
    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant. Generate inspiring, appreciative messages for GitHub contributors.",
        },
        {
            "role": "user",
            "content": (
                f"Write a warm thank-you comment for the merged PR {pr_url} by {pr_credit}. "
                f"Context:\n{pr_summary}\n\n"
                f"Start with an enthusiastic note about the merge, incorporate a relevant inspirational quote from a historical "
                f"figure, and connect it to the PR's impact. Keep it concise yet meaningful, ensuring contributors feel valued."
            ),
        },
    ]
    return get_response(messages)


def generate_issue_comment(pr_url, pr_summary, pr_credit, pr_title=""):
    """Generates personalized issue comment based on PR context."""
    repo_parts = pr_url.split("/repos/")[1].split("/pulls/")[0] if "/repos/" in pr_url else ""
    owner_repo = repo_parts.split("/")
    repo_name = owner_repo[-1] if len(owner_repo) > 1 else "package"

    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant. Generate friendly GitHub issue comments. No @ mentions or direct addressing.",
        },
        {
            "role": "user",
            "content": f"Write a GitHub issue comment announcing a potential fix for this issue is now merged in linked PR {pr_url} by {pr_credit}\n\n"
            f"PR Title: {pr_title}\n\n"
            f"Context from PR:\n{pr_summary}\n\n"
            f"Include:\n"
            f"1. An explanation of key changes from the PR that may resolve this issue\n"
            f"2. Credit to the PR author and contributors\n"
            f"3. Options for testing if PR changes have resolved this issue:\n"
            f"   - If the PR mentions a specific version number (like v8.0.0 or 3.1.0), include: pip install -U {repo_name}>=VERSION\n"
            f"   - Also suggest: pip install git+https://github.com/{repo_parts}.git@main\n"
            f"   - If appropriate, mention they can also wait for the next official PyPI release\n"
            f"4. Request feedback on whether the PR changes resolve the issue\n"
            f"5. Thank 🙏 for reporting the issue and welcome any further feedback if the issue persists\n\n",
        },
    ]
    return get_response(messages)


def generate_pr_summary(repository, diff_text):
    """Generates a concise, professional summary of a PR using OpenAI's API."""
    prompt, is_large, skipped_files = get_pr_summary_prompt(repository, diff_text)

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
    if not pr_credit:
        return None

    comment = generate_issue_comment(data["url"], pr_summary, pr_credit, data.get("title") or "")

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
    if event.should_skip_openai():
        return

    print(f"Retrieving diff for PR {event.pr['number']}")
    diff = event.get_pr_diff()

    # Generate PR summary
    print("Generating PR summary...")
    summary = generate_pr_summary(event.repository, diff)

    # Update PR description
    print("Updating PR description...")
    event.update_pr_description(event.pr["number"], summary)

    if event.pr.get("merged"):
        print("PR is merged, labeling fixed issues...")
        pr_credit = label_fixed_issues(event, summary)
        print("Removing TODO label from PR...")
        event.remove_labels(event.pr["number"], labels=("TODO",))
        if pr_credit:
            print("Posting PR author thank you message...")
            pr_url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{event.pr['number']}"
            message = generate_merge_message(summary, pr_credit, pr_url)
            event.add_comment(event.pr["number"], None, message, "pull request")


if __name__ == "__main__":
    main()
