# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import time

from .first_interaction import apply_labels, get_first_interaction_response, get_relevant_labels
from .utils import GITHUB_API_URL, GITHUB_GRAPHQL_URL, Action, get_completion

# Constants
SUMMARY_START = (
    "## 🛠️ PR Summary\n\n<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)<sub>\n\n"
)


def generate_unified_pr_response(event):
    """Generate PR summary, labels, and first comment in a single OpenAI call."""
    pr_data = event.get_repo_data(f"pulls/{event.pr['number']}")
    available_labels = event.get_repo_data("labels")

    # Single prompt for all three outputs
    prompt = f"""Analyze this {event.repository} PR and respond with JSON:

{{
    "summary": "### 🌟 Summary\\n[brief description]\\n### 📊 Key Changes\\n- [key changes]\\n### 🎯 Purpose & Impact\\n- [impact on users]",
    "labels": ["relevant", "labels"],
    "first_comment": "👋 Hello @{pr_data["user"]["login"]}, thank you for your PR! [include checklist and guidance]"
}}

Title: {pr_data["title"]}
Body: {pr_data.get("body", "")[:2000]}
Labels: {", ".join([l["name"] for l in available_labels[:20]])}
Diff: {event.get_pr_diff()}"""

    try:
        response = get_completion(
            [
                {"role": "system", "content": "You are an Ultralytics AI assistant for GitHub PR analysis."},
                {"role": "user", "content": prompt},
            ]
        )
        data = json.loads(response)

        summary = SUMMARY_START + data.get("summary", "")
        labels = [l for l in data.get("labels", []) if l in {label["name"] for label in available_labels}]
        comment = data.get("first_comment", "")

        return summary, labels, comment

    except Exception as e:
        print(f"Unified call failed ({e}), using individual functions")
        # Fallback to existing individual functions
        summary = generate_pr_summary(event.repository, event.get_pr_diff())
        labels = get_relevant_labels(
            "pull request",
            pr_data["title"],
            pr_data.get("body", ""),
            {l["name"]: l.get("description", "") for l in available_labels},
            [],
        )
        comment = get_first_interaction_response(
            event, "pull request", pr_data["title"], pr_data.get("body", ""), pr_data["user"]["login"]
        )
        return summary, labels, comment


# Keep all existing functions unchanged
def generate_merge_message(pr_summary=None, pr_credit=None, pr_url=None):
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
    return get_completion(messages)


def post_merge_message(event, summary, pr_credit):
    """Posts thank you message on PR after merge."""
    pr_url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{event.pr['number']}"
    comment_url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{event.pr['number']}/comments"
    message = generate_merge_message(summary, pr_credit, pr_url)
    event.post(comment_url, json={"body": message})


def generate_issue_comment(pr_url, pr_summary, pr_credit, pr_title=""):
    """Generates personalized issue comment based on PR context."""
    repo_parts = pr_url.split("/repos/")[1].split("/pulls/")[0] if "/repos/" in pr_url else ""
    repo_name = repo_parts.split("/")[-1] if repo_parts else "package"

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
    return get_completion(messages)


def generate_pr_summary(repository, diff_text):
    """Generates a concise, professional summary of a PR using OpenAI's API for Ultralytics repositories."""
    if not diff_text:
        diff_text = "**ERROR: DIFF IS EMPTY, THERE ARE ZERO CODE CHANGES IN THIS PR."

    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant skilled in software development and technical communication. Your task is to summarize GitHub PRs from Ultralytics in a way that is accurate, concise, and understandable to both expert developers and non-expert users. Focus on highlighting the key changes and their impact in simple, concise terms.",
        },
        {
            "role": "user",
            "content": f"Summarize this '{repository}' PR, focusing on major changes, their purpose, and potential impact. Keep the summary clear and concise, suitable for a broad audience. Add emojis to enliven the summary. Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
            f"### 🌟 Summary (single-line synopsis)\n"
            f"### 📊 Key Changes (bullet points highlighting any major changes)\n"
            f"### 🎯 Purpose & Impact (bullet points explaining any benefits and potential impact to users)\n"
            f"\n\nHere's the PR diff:\n\n{diff_text}",
        },
    ]
    reply = get_completion(messages, temperature=1.0)
    if len(diff_text) == 90000:
        reply = "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + reply
    return SUMMARY_START + reply


def update_pr_description(event, new_summary, max_retries=2):
    """Updates PR description with new summary, retrying if description is None."""
    description = ""
    url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{event.pr['number']}"
    for i in range(max_retries + 1):
        description = event.get(url).json().get("body") or ""
        if description:
            break
        if i < max_retries:
            print("No current PR description found, retrying...")
            time.sleep(1)

    # Check if existing summary is present and update accordingly
    start = "## 🛠️ PR Summary"
    if start in description:
        print("Existing PR Summary found, replacing.")
        updated_description = description.split(start)[0] + new_summary
    else:
        print("PR Summary not found, appending.")
        updated_description = description + "\n\n" + new_summary

    # Update the PR description
    event.patch(url, json={"body": updated_description})


def label_fixed_issues(event, pr_summary):
    """Labels issues closed by PR when merged, notifies users, and returns PR contributors."""
    query = """
query($owner: String!, $repo: String!, $pr_number: Int!) {
    repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr_number) {
            closingIssuesReferences(first: 50) { nodes { number } }
            url
            title
            body
            author { login, __typename }
            reviews(first: 50) { nodes { author { login, __typename } } }
            comments(first: 50) { nodes { author { login, __typename } } }
            commits(first: 100) { nodes { commit { author { user { login } }, committer { user { login } } } } }
        }
    }
}
"""
    owner, repo = event.repository.split("/")
    variables = {"owner": owner, "repo": repo, "pr_number": event.pr["number"]}
    response = event.post(GITHUB_GRAPHQL_URL, json={"query": query, "variables": variables})
    if response.status_code != 200:
        return None  # no linked issues

    try:
        data = response.json()["data"]["repository"]["pullRequest"]
        comments = data["reviews"]["nodes"] + data["comments"]["nodes"]
        token_username = event.get_username()  # get GITHUB_TOKEN username
        author = data["author"]["login"] if data["author"]["__typename"] != "Bot" else None
        pr_title = data.get("title", "")

        # Get unique contributors from reviews and comments
        contributors = {x["author"]["login"] for x in comments if x["author"]["__typename"] != "Bot"}

        # Add commit authors and committers that have GitHub accounts linked
        for commit in data["commits"]["nodes"]:
            commit_data = commit["commit"]
            for user_type in ["author", "committer"]:
                if user := commit_data[user_type].get("user"):
                    if login := user.get("login"):
                        contributors.add(login)

        contributors.discard(author)
        contributors.discard(token_username)

        # Write credit string
        pr_credit = ""  # i.e. "@user1 with contributions from @user2, @user3"
        if author and author != token_username:
            pr_credit += f"@{author}"
        if contributors:
            pr_credit += (" with contributions from " if pr_credit else "") + ", ".join(f"@{c}" for c in contributors)

        # Generate personalized comment
        comment = generate_issue_comment(
            pr_url=data["url"], pr_summary=pr_summary, pr_credit=pr_credit, pr_title=pr_title
        )

        # Update linked issues
        for issue in data["closingIssuesReferences"]["nodes"]:
            number = issue["number"]
            # Add fixed label
            event.post(f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/labels", json={"labels": ["fixed"]})

            # Add comment
            event.post(f"{GITHUB_API_URL}/repos/{event.repository}/issues/{number}/comments", json={"body": comment})

        return pr_credit
    except KeyError as e:
        print(f"Error parsing GraphQL response: {e}")
        return None


def remove_pr_labels(event, labels=()):
    """Removes specified labels from PR."""
    for label in labels:  # Can be extended with more labels in the future
        event.delete(f"{GITHUB_API_URL}/repos/{event.repository}/issues/{event.pr['number']}/labels/{label}")


def main(*args, **kwargs):
    """Summarize and label a PR and respond to the author."""
    event = Action(*args, **kwargs)
    action = event.event_data.get("action", "")

    # Unified approach for opened PRs (summary + labels + comment)
    print(f"Processing PR {event.pr['number']} with action: {action}")
    if action == "opened":
        summary, labels, first_comment = generate_unified_pr_response(event)

        # Apply all results
        update_pr_description(event, summary)
        if labels:
            apply_labels(event, event.pr["number"], None, labels, "pull request")
        if first_comment:
            comment_url = f"{GITHUB_API_URL}/repos/{event.repository}/issues/{event.pr['number']}/comments"
            event.post(comment_url, json={"body": first_comment})

    # Other actions
    elif action in ["synchronize", "edited"]:
        print("Updating PR summary...")
        summary = generate_pr_summary(event.repository, event.get_pr_diff())
        update_pr_description(event, summary)

    # Update linked issues and post thank you message if merged
    elif event.pr.get("merged"):
        print("PR is merged, labeling fixed issues...")
        summary = generate_pr_summary(event.repository, event.get_pr_diff())
        pr_credit = label_fixed_issues(event, summary)
        print("Removing TODO label from PR...")
        remove_pr_labels(event, labels=["TODO"])
        if pr_credit:
            print("Posting PR author thank you message...")
            post_merge_message(event, summary, pr_credit)


if __name__ == "__main__":
    main()
