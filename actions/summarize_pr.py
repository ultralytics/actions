# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import requests

from .utils import (
    GITHUB_API_URL,
    GITHUB_HEADERS,
    PR_NUMBER,
    REPO_NAME,
    get_completion,
    get_pr_diff,
)

# Action settings
SUMMARY_START = (
    "## 🛠️ PR Summary\n\n<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)<sub>\n\n"
)


def generate_pr_summary(repo_name, diff_text):
    """Generates a professionally written yet accessible summary of a PR using OpenAI's API."""
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
        return SUMMARY_START + "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + reply
    else:
        return SUMMARY_START + reply


def update_pr_description(repo_name, pr_number, new_summary):
    """Updates the original PR description with a new summary, replacing an existing summary if found."""
    # Fetch the current PR description
    pr_url = f"{GITHUB_API_URL}/repos/{repo_name}/pulls/{pr_number}"
    pr_response = requests.get(pr_url, headers=GITHUB_HEADERS)
    pr_data = pr_response.json()
    current_description = pr_data.get("body") or ""  # warning, can be None

    # Check if existing summary is present and update accordingly
    if SUMMARY_START in current_description:
        updated_description = current_description.split(SUMMARY_START)[0] + new_summary
    else:
        updated_description = current_description + "\n\n" + new_summary

    # Update the PR description
    update_response = requests.patch(pr_url, json={"body": updated_description}, headers=GITHUB_HEADERS)
    return update_response.status_code


def main():
    """Summarize PR."""
    diff = get_pr_diff(PR_NUMBER)

    # Generate PR summary
    summary = generate_pr_summary(REPO_NAME, diff)

    # Update PR description
    status_code = update_pr_description(REPO_NAME, PR_NUMBER, summary)
    if status_code == 200:
        print("PR description updated successfully.")
    else:
        print(f"Failed to update PR description. Status code: {status_code}")


if __name__ == "__main__":
    main()
