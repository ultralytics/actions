# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import time

from .utils import GITHUB_API_URL, GITHUB_GRAPHQL_URL, Action, get_completion

# Constants
SUMMARY_START = (
    "## 🛠️ PR Summary\n\n<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)<sub>\n\n"
)


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
    # Extract repo info from PR URL (format: api.github.com/repos/owner/repo/pulls/number)
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
    return get_completion(messages)


def generate_pr_summary(repository, diff_text):
    """Generates a concise, professional summary of a PR using OpenAI's API for Ultralytics repositories."""
    if not diff_text:
        diff_text = "**ERROR: DIFF IS EMPTY, THERE ARE ZERO CODE CHANGES IN THIS PR."
    ratio = 3.3  # about 3.3 characters per token
    limit = round(128000 * ratio * 0.5)  # use up to 50% of the 128k context window for prompt
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
            f"\n\nHere's the PR diff:\n\n{diff_text[:limit]}",
        },
    ]
    reply = get_completion(messages, temperature=0.2)
    if len(diff_text) > limit:
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
    """Summarize a pull request and update its description with a summary."""
    event = Action(*args, **kwargs)

    print(f"Retrieving diff for PR {event.pr['number']}")
    diff = event.get_pr_diff()

    # Generate PR summary
    print("Generating PR summary...")
    summary = generate_pr_summary(event.repository, diff)

    # Update PR description
    print("Updating PR description...")
    update_pr_description(event, summary)

    # Update linked issues and post thank you message if merged
    if event.pr.get("merged"):
        print("PR is merged, labeling fixed issues...")
        pr_credit = label_fixed_issues(event, summary)
        print("Removing TODO label from PR...")
        remove_pr_labels(event, labels=["TODO"])
        if pr_credit:
            print("Posting PR author thank you message...")
            post_merge_message(event, summary, pr_credit)


if __name__ == "__main__":
    main()
