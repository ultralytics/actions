# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import os
import re
import subprocess
import time
from datetime import datetime

import requests

from .utils import (
    GITHUB_API_URL,
    GITHUB_HEADERS,
    GITHUB_HEADERS_DIFF,
    GITHUB_REPOSITORY,
    GITHUB_TOKEN,
    get_completion,
    remove_html_comments,
)

# Environment variables
CURRENT_TAG = os.getenv("CURRENT_TAG")
PREVIOUS_TAG = os.getenv("PREVIOUS_TAG")


def get_release_diff(repo_name: str, previous_tag: str, latest_tag: str) -> str:
    """Retrieves the differences between two specified Git tags in a GitHub repository."""
    url = f"{GITHUB_API_URL}/repos/{repo_name}/compare/{previous_tag}...{latest_tag}"
    r = requests.get(url, headers=GITHUB_HEADERS_DIFF)
    return r.text if r.status_code == 200 else f"Failed to get diff: {r.content}"


def get_prs_between_tags(repo_name: str, previous_tag: str, latest_tag: str) -> list:
    """Retrieves and processes pull requests merged between two specified tags in a GitHub repository."""
    url = f"{GITHUB_API_URL}/repos/{repo_name}/compare/{previous_tag}...{latest_tag}"
    r = requests.get(url, headers=GITHUB_HEADERS)
    r.raise_for_status()

    data = r.json()
    pr_numbers = set()

    for commit in data["commits"]:
        pr_matches = re.findall(r"#(\d+)", commit["commit"]["message"])
        pr_numbers.update(pr_matches)

    prs = []
    time.sleep(10)  # sleep 10 seconds to allow final PR summary to update on merge
    for pr_number in sorted(pr_numbers):  # earliest to latest
        pr_url = f"{GITHUB_API_URL}/repos/{repo_name}/pulls/{pr_number}"
        pr_response = requests.get(pr_url, headers=GITHUB_HEADERS)
        if pr_response.status_code == 200:
            pr_data = pr_response.json()
            prs.append(
                {
                    "number": pr_data["number"],
                    "title": pr_data["title"],
                    "body": remove_html_comments(pr_data["body"]),
                    "author": pr_data["user"]["login"],
                    "html_url": pr_data["html_url"],
                    "merged_at": pr_data["merged_at"],
                }
            )

    # Sort PRs by merge date
    prs.sort(key=lambda x: datetime.strptime(x["merged_at"], "%Y-%m-%dT%H:%M:%SZ"))

    return prs


def get_new_contributors(repo: str, prs: list) -> set:
    """Identify new contributors who made their first merged PR in the current release."""
    new_contributors = set()
    for pr in prs:
        author = pr["author"]
        # Check if this is the author's first contribution
        url = f"{GITHUB_API_URL}/search/issues?q=repo:{repo}+author:{author}+is:pr+is:merged&sort=created&order=asc"
        r = requests.get(url, headers=GITHUB_HEADERS)
        if r.status_code == 200:
            data = r.json()
            if data["total_count"] > 0:
                first_pr = data["items"][0]
                if first_pr["number"] == pr["number"]:
                    new_contributors.add(author)
    return new_contributors


def generate_release_summary(diff: str, prs: list, latest_tag: str, previous_tag: str, repo_name: str) -> str:
    """Generate a concise release summary with key changes, purpose, and impact for a new Ultralytics version."""
    pr_summaries = "\n\n".join(
        [f"PR #{pr['number']}: {pr['title']} by @{pr['author']}\n{pr['body'][:1000]}" for pr in prs]
    )

    current_pr = prs[-1] if prs else None
    current_pr_summary = (
        f"Current PR #{current_pr['number']}: {current_pr['title']} by @{current_pr['author']}\n{current_pr['body'][:1000]}"
        if current_pr
        else "No current PR found."
    )

    whats_changed = "\n".join([f"* {pr['title']} by @{pr['author']} in {pr['html_url']}" for pr in prs])

    # Generate New Contributors section
    new_contributors = get_new_contributors(repo_name, prs)
    new_contributors_section = (
        "\n## New Contributors\n"
        + "\n".join(
            [
                f"* @{contributor} made their first contribution in {next(pr['html_url'] for pr in prs if pr['author'] == contributor)}"
                for contributor in new_contributors
            ]
        )
        if new_contributors
        else ""
    )

    full_changelog = f"https://github.com/{repo_name}/compare/{previous_tag}...{latest_tag}"
    release_suffix = (
        f"\n\n## What's Changed\n{whats_changed}\n{new_contributors_section}\n\n**Full Changelog**: {full_changelog}\n"
    )

    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant skilled in software development and technical communication. Your task is to summarize GitHub releases in a way that is detailed, accurate, and understandable to both expert developers and non-expert users. Focus on highlighting the key changes and their impact in simple and intuitive terms.",
        },
        {
            "role": "user",
            "content": f"Summarize the updates made in the '{latest_tag}' tag, focusing on major model or features changes, their purpose, and potential impact. Keep the summary clear and suitable for a broad audience. Add emojis to enliven the summary. Prioritize changes from the current PR (the first in the list), which is usually the most important in the release. Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
            f"## 🌟 Summary (single-line synopsis)\n"
            f"## 📊 Key Changes (bullet points highlighting any major changes)\n"
            f"## 🎯 Purpose & Impact (bullet points explaining any benefits and potential impact to users)\n\n\n"
            f"Here's the information about the current PR:\n\n{current_pr_summary}\n\n"
            f"Here's the information about PRs merged between the previous release and this one:\n\n{pr_summaries[:30000]}\n\n"
            f"Here's the release diff:\n\n{diff[:300000]}",
        },
    ]
    print(messages[-1]["content"])  # for debug
    return get_completion(messages) + release_suffix


def create_github_release(repo_name: str, tag_name: str, name: str, body: str) -> int:
    """Creates a GitHub release with specified tag, name, and body content for the given repository."""
    url = f"{GITHUB_API_URL}/repos/{repo_name}/releases"
    data = {"tag_name": tag_name, "name": name, "body": body, "draft": False, "prerelease": False}
    r = requests.post(url, headers=GITHUB_HEADERS, json=data)
    return r.status_code


def get_previous_tag() -> str:
    """Retrieves the previous Git tag, excluding the current tag, using the git describe command."""
    cmd = ["git", "describe", "--tags", "--abbrev=0", "--exclude", CURRENT_TAG]
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.strip()
    except subprocess.CalledProcessError:
        print("Failed to get previous tag from git. Using previous commit.")
        return "HEAD~1"


def main():
    """Automates generating and publishing a GitHub release summary from PRs and commit differences."""
    if not all([GITHUB_TOKEN, CURRENT_TAG]):
        raise ValueError("One or more required environment variables are missing.")

    previous_tag = PREVIOUS_TAG or get_previous_tag()

    # Get the diff between the tags
    diff = get_release_diff(GITHUB_REPOSITORY, previous_tag, CURRENT_TAG)

    # Get PRs merged between the tags
    prs = get_prs_between_tags(GITHUB_REPOSITORY, previous_tag, CURRENT_TAG)

    # Generate release summary
    try:
        summary = generate_release_summary(diff, prs, CURRENT_TAG, previous_tag, GITHUB_REPOSITORY)
    except Exception as e:
        print(f"Failed to generate summary: {str(e)}")
        summary = "Failed to generate summary."

    # Get the latest commit message
    cmd = ["git", "log", "-1", "--pretty=%B"]
    commit_message = subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.split("\n")[0].strip()

    # Create the release on GitHub
    status_code = create_github_release(GITHUB_REPOSITORY, CURRENT_TAG, f"{CURRENT_TAG} - {commit_message}", summary)
    if status_code == 201:
        print(f"Successfully created release {CURRENT_TAG}")
    else:
        print(f"Failed to create release {CURRENT_TAG}. Status code: {status_code}")


if __name__ == "__main__":
    main()
