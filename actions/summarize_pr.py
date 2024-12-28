# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import time

import requests

from .utils import (
    GITHUB_API_URL,
    Action,
    get_completion,
)

# Constants
SUMMARY_START = (
    "## 🛠️ PR Summary\n\n<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)<sub>\n\n"
)


def generate_merge_message(pr_summary=None, pr_credit=None):
    """Generates a thank-you message for merged PR contributors."""
    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant. Generate meaningful, inspiring messages to GitHub users.",
        },
        {
            "role": "user",
            "content": f"Write a friendly thank you for a merged GitHub PR by {pr_credit}. "
            f"Context from PR:\n{pr_summary}\n\n"
            f"Start with the exciting message that this PR is now merged, and weave in an inspiring but obscure quote "
            f"from a historical figure in science, art, stoicism and philosophy. "
            f"Keep the message concise yet relevant to the specific contributions in this PR. "
            f"We want the contributors to feel their effort is appreciated and will make a difference in the world.",
        },
    ]
    return get_completion(messages)


def post_merge_message(pr_number, repository, summary, pr_credit, headers):
    """Posts thank you message on PR after merge."""
    message = generate_merge_message(summary, pr_credit)
    comment_url = f"{GITHUB_API_URL}/repos/{repository}/issues/{pr_number}/comments"
    response = requests.post(comment_url, json={"body": message}, headers=headers)
    return response.status_code == 201


def generate_issue_comment(pr_url, pr_summary, pr_credit):
    """Generates a personalized issue comment using based on the PR context."""
    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant. Generate friendly GitHub issue comments. No @ mentions or direct addressing.",
        },
        {
            "role": "user",
            "content": f"Write a GitHub issue comment announcing a potential fix for this issue is now merged in linked PR {pr_url} by {pr_credit}\n\n"
            f"Context from PR:\n{pr_summary}\n\n"
            f"Include:\n"
            f"1. An explanation of key changes from the PR that may resolve this issue\n"
            f"2. Credit to the PR author and contributors\n"
            f"3. Options for testing if PR changes have resolved this issue:\n"
            f"   - pip install git+https://github.com/ultralytics/ultralytics.git@main # test latest changes\n"
            f"   - or await next official PyPI release\n"
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
    reply = get_completion(messages)
    if len(diff_text) > limit:
        reply = "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + reply
    return SUMMARY_START + reply


def update_pr_description(repository, pr_number, new_summary, headers, max_retries=2):
    """Updates PR description with new summary, retrying if description is None."""
    pr_url = f"{GITHUB_API_URL}/repos/{repository}/pulls/{pr_number}"
    description = ""
    for i in range(max_retries + 1):
        description = requests.get(pr_url, headers=headers).json().get("body") or ""
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
    update_response = requests.patch(pr_url, json={"body": updated_description}, headers=headers)
    return update_response.status_code


def label_fixed_issues(repository, pr_number, pr_summary, headers, action):
    """Labels issues closed by PR when merged, notifies users, returns PR contributors."""
    query = """
query($owner: String!, $repo: String!, $pr_number: Int!) {
    repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr_number) {
            closingIssuesReferences(first: 50) { nodes { number } }
            url
            body
            author { login, __typename }
            reviews(first: 50) { nodes { author { login, __typename } } }
            comments(first: 50) { nodes { author { login, __typename } } }
            commits(first: 100) { nodes { commit { author { user { login } }, committer { user { login } } } } }
        }
    }
}
"""
    owner, repo = repository.split("/")
    variables = {"owner": owner, "repo": repo, "pr_number": pr_number}
    graphql_url = "https://api.github.com/graphql"
    response = requests.post(graphql_url, json={"query": query, "variables": variables}, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch linked issues. Status code: {response.status_code}")
        return [], None

    try:
        data = response.json()["data"]["repository"]["pullRequest"]
        comments = data["reviews"]["nodes"] + data["comments"]["nodes"]
        token_username = action.get_username()  # get GITHUB_TOKEN username
        author = data["author"]["login"] if data["author"]["__typename"] != "Bot" else None

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
        comment = generate_issue_comment(pr_url=data["url"], pr_summary=pr_summary, pr_credit=pr_credit)

        # Update linked issues
        for issue in data["closingIssuesReferences"]["nodes"]:
            issue_number = issue["number"]
            # Add fixed label
            label_url = f"{GITHUB_API_URL}/repos/{repository}/issues/{issue_number}/labels"
            label_response = requests.post(label_url, json={"labels": ["fixed"]}, headers=headers)

            # Add comment
            comment_url = f"{GITHUB_API_URL}/repos/{repository}/issues/{issue_number}/comments"
            comment_response = requests.post(comment_url, json={"body": comment}, headers=headers)

            if label_response.status_code == 200 and comment_response.status_code == 201:
                print(f"Added 'fixed' label and comment to issue #{issue_number}")
            else:
                print(
                    f"Failed to update issue #{issue_number}. Label status: {label_response.status_code}, "
                    f"Comment status: {comment_response.status_code}"
                )

        return pr_credit
    except KeyError as e:
        print(f"Error parsing GraphQL response: {e}")
        return [], None


def remove_todos_on_merge(pr_number, repository, headers):
    """Removes specified labels from PR."""
    for label in ["TODO"]:  # Can be extended with more labels in the future
        requests.delete(f"{GITHUB_API_URL}/repos/{repository}/issues/{pr_number}/labels/{label}", headers=headers)


def main(*args, **kwargs):
    """Summarize a pull request and update its description with a summary."""
    action = Action(*args, **kwargs)
    pr_number = action.pr["number"]
    headers = action.headers
    repository = action.repository

    print(f"Retrieving diff for PR {pr_number}")
    diff = action.get_pr_diff()

    # Generate PR summary
    print("Generating PR summary...")
    summary = generate_pr_summary(repository, diff)

    # Update PR description
    print("Updating PR description...")
    status_code = update_pr_description(repository, pr_number, summary, headers)
    if status_code == 200:
        print("PR description updated successfully.")
    else:
        print(f"Failed to update PR description. Status code: {status_code}")

    # Update linked issues and post thank you message if merged
    if action.pr.get("merged"):
        print("PR is merged, labeling fixed issues...")
        pr_credit = label_fixed_issues(repository, pr_number, summary, headers, action)
        print("Removing TODO label from PR...")
        remove_todos_on_merge(pr_number, repository, headers)
        if pr_credit:
            print("Posting PR author thank you message...")
            post_merge_message(pr_number, repository, summary, pr_credit, headers)


if __name__ == "__main__":
    main()
