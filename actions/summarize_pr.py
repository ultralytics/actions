# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import time

import requests

from .utils import (
    GITHUB_API_URL,
    GITHUB_HEADERS,
    GITHUB_REPOSITORY,
    PR,
    get_completion,
    get_pr_diff,
)

# Constants
SUMMARY_START = (
    "## 🛠️ PR Summary\n\n<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)<sub>\n\n"
)


def generate_pr_summary(repo_name, diff_text):
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
            "content": f"Summarize this '{repo_name}' PR, focusing on major changes, their purpose, and potential impact. Keep the summary clear and concise, suitable for a broad audience. Add emojis to enliven the summary. Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
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


def update_pr_description(repo_name, pr_number, new_summary, max_retries=2):
    """Updates PR description with new summary, retrying if description is None."""
    pr_url = f"{GITHUB_API_URL}/repos/{repo_name}/pulls/{pr_number}"
    description = ""
    for i in range(max_retries + 1):
        description = requests.get(pr_url, headers=GITHUB_HEADERS).json().get("body") or ""
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
    update_response = requests.patch(pr_url, json={"body": updated_description}, headers=GITHUB_HEADERS)
    return update_response.status_code


def label_fixed_issues(pr_number):
    """Labels issues that are closed by this PR when it's merged."""
    # GraphQL query to get closing issues
    query = """
query($owner: String!, $repo: String!, $pr_number: Int!) {
    repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr_number) {
            closingIssuesReferences(first: 50) {
                nodes {
                    number
                }
            }
        }
    }
}
"""

    owner, repo = GITHUB_REPOSITORY.split("/")
    variables = {"owner": owner, "repo": repo, "pr_number": pr_number}
    graphql_url = "https://api.github.com/graphql"
    response = requests.post(graphql_url, json={"query": query, "variables": variables}, headers=GITHUB_HEADERS)
    if response.status_code != 200:
        print(f"Failed to fetch linked issues. Status code: {response.status_code}")
        return

    try:
        issues = response.json()["data"]["repository"]["pullRequest"]["closingIssuesReferences"]["nodes"]
        for issue in issues:
            issue_number = issue["number"]
            label_url = f"{GITHUB_API_URL}/repos/{GITHUB_REPOSITORY}/issues/{issue_number}/labels"
            label_response = requests.post(label_url, json={"labels": ["fixed"]}, headers=GITHUB_HEADERS)
            if label_response.status_code == 200:
                print(f"Added 'fixed' label to issue #{issue_number}")
            else:
                print(f"Failed to add label to issue #{issue_number}. Status: {label_response.status_code}")
    except KeyError as e:
        print(f"Error parsing GraphQL response: {e}")
        return


def remove_todos_on_merge(pr_number):
    """Removes specified labels from PR."""
    for label in ["TODO"]:  # Can be extended with more labels in the future
        requests.delete(
            f"{GITHUB_API_URL}/repos/{GITHUB_REPOSITORY}/issues/{pr_number}/labels/{label}", headers=GITHUB_HEADERS
        )


def main():
    """Summarize a pull request and update its description with an AI-generated summary."""
    pr_number = PR["number"]

    print(f"Retrieving diff for PR {pr_number}")
    diff = get_pr_diff(pr_number)

    # Generate PR summary
    print("Generating PR summary...")
    summary = generate_pr_summary(GITHUB_REPOSITORY, diff)

    # Update PR description
    print("Updating PR description...")
    status_code = update_pr_description(GITHUB_REPOSITORY, pr_number, summary)
    if status_code == 200:
        print("PR description updated successfully.")
    else:
        print(f"Failed to update PR description. Status code: {status_code}")

    # Update linked issues
    if PR.get("merged"):
        print("PR is merged, labeling fixed issues...")
        label_fixed_issues(pr_number)
        print("Removing TODO label from PR...")
        remove_todos_on_merge(pr_number)


if __name__ == "__main__":
    main()
