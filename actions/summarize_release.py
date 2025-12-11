# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime

from .utils import GITHUB_API_URL, Action, get_response, remove_html_comments

# Environment variables
CURRENT_TAG = os.getenv("CURRENT_TAG")
PREVIOUS_TAG = os.getenv("PREVIOUS_TAG")


def get_release_diff(event, previous_tag: str, latest_tag: str) -> str:
    """Retrieves the differences between two specified Git tags in a GitHub repository."""
    url = f"{GITHUB_API_URL}/repos/{event.repository}/compare/{previous_tag}...{latest_tag}"
    r = event.get(url, headers=event.headers_diff)
    return r.text if r.status_code == 200 else f"Failed to get diff: {r.text}"


def get_prs_between_tags(event, previous_tag: str, latest_tag: str) -> list:
    """Retrieves and processes pull requests merged between two specified tags in a GitHub repository."""
    url = f"{GITHUB_API_URL}/repos/{event.repository}/compare/{previous_tag}...{latest_tag}"
    r = event.get(url)

    if r.status_code != 200:
        print(f"Failed to get comparison between {previous_tag} and {latest_tag}, status: {r.status_code}")
        return []

    data = r.json()
    if "commits" not in data:
        print(f"No commits found in comparison between {previous_tag} and {latest_tag}")
        return []

    pr_numbers = set()
    for commit in data["commits"]:
        pr_matches = re.findall(r"#(\d+)", commit["commit"]["message"])
        pr_numbers.update(pr_matches)

    prs = []
    for pr_number in sorted(pr_numbers):  # earliest to latest
        time.sleep(1)  # Rate limit: GitHub search API has strict limits
        pr_url = f"{GITHUB_API_URL}/repos/{event.repository}/pulls/{pr_number}"
        pr_response = event.get(pr_url)
        if pr_response.status_code == 200:
            pr_data = pr_response.json()
            prs.append(
                {
                    "number": pr_data["number"],
                    "title": pr_data["title"],
                    "body": remove_html_comments(pr_data.get("body") or ""),
                    "author": pr_data["user"]["login"],
                    "html_url": pr_data["html_url"],
                    "merged_at": pr_data["merged_at"],
                }
            )

    # Sort PRs by merge date
    prs.sort(key=lambda x: datetime.strptime(x["merged_at"], "%Y-%m-%dT%H:%M:%SZ"))

    return prs


def get_new_contributors(event, prs: list) -> set:
    """Identify new contributors who made their first merged PR in the current release."""
    new_contributors = set()
    checked_authors = set()
    for pr in prs:
        author = pr["author"]
        if author in checked_authors:
            print(f"Skipping duplicate author: {author}")
            continue
        checked_authors.add(author)

        time.sleep(2)  # Rate limit: GitHub search API has strict limits
        url = f"{GITHUB_API_URL}/search/issues?q=repo:{event.repository}+author:{author}+is:pr+is:merged&sort=created&order=asc"
        r = event.get(url)
        if r.status_code == 200:
            data = r.json()
            if data["total_count"] > 0:
                first_pr = data["items"][0]
                if first_pr["number"] == pr["number"]:
                    new_contributors.add(author)
        elif r.status_code == 403:
            print(f"⚠️ Rate limit hit checking {author}, stopping contributor check")
            break
        else:
            print(f"Failed to check {author}: {r.status_code}")
    return new_contributors


def generate_release_summary(
    event,
    diff: str,
    prs: list,
    latest_tag: str,
    previous_tag: str,
) -> str:
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
    new_contributors = get_new_contributors(event, prs)
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

    full_changelog = f"https://github.com/{event.repository}/compare/{previous_tag}...{latest_tag}"
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
            "content": f"Summarize the updates made in the '{latest_tag}' tag, focusing on major model or features changes, their purpose, and potential impact. Keep the summary clear and suitable for a broad audience. Add emojis to enliven the summary. Prioritize changes from the current PR (the last in the list), which is usually the most important in the release. Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
            f"## 🌟 Summary (single-line synopsis)\n"
            f"## 📊 Key Changes (bullet points highlighting any major changes)\n"
            f"## 🎯 Purpose & Impact (bullet points explaining any benefits and potential impact to users)\n\n\n"
            f"Here's the information about the current PR:\n\n{current_pr_summary}\n\n"
            f"Here's the information about PRs merged between the previous release and this one:\n\n{pr_summaries[:30000]}\n\n"
            f"Here's the release diff:\n\n{diff[:300000]}",
        },
    ]
    # print(messages[-1]["content"])  # for debug
    return get_response(messages, temperature=1.0) + release_suffix


def create_github_release(event, tag_name: str, name: str, body: str):
    """Creates a GitHub release with specified tag, name, and body content for the given repository."""
    url = f"{GITHUB_API_URL}/repos/{event.repository}/releases"
    data = {"tag_name": tag_name, "name": name, "body": body, "draft": False, "prerelease": False}
    event.post(url, json=data)


def get_actual_previous_tag(current_tag: str) -> str:
    """Gets the actual previous tag or commit SHA using git, excluding the current tag."""
    try:
        return subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--exclude", current_tag],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        # No previous tag - try first commit for first release
        try:
            first = subprocess.run(
                ["git", "rev-list", "--max-parents=0", "HEAD"], check=True, text=True, capture_output=True
            ).stdout.split()[0]
            print(f"No previous tag found. Using first commit: {first[:7]}")
            return first
        except (subprocess.CalledProcessError, IndexError):
            # Fallback for shallow clones - GitHub API accepts HEAD~1 even if git can't verify locally
            print("Warning: Could not determine first commit, using HEAD~1")
            return "HEAD~1"


def main(*args, **kwargs):
    """Automates generating and publishing a GitHub release summary from PRs and commit differences."""
    event = Action(*args, **kwargs)

    if not all([event.token, CURRENT_TAG]):
        raise ValueError("One or more required environment variables are missing.")

    # Try PREVIOUS_TAG first, fall back to actual previous tag if comparison fails
    previous_tag = PREVIOUS_TAG or get_actual_previous_tag(CURRENT_TAG)

    # Test if the previous tag works for comparison
    test_url = f"{GITHUB_API_URL}/repos/{event.repository}/compare/{previous_tag}...{CURRENT_TAG}"
    if event.get(test_url).status_code != 200:
        previous_tag = get_actual_previous_tag(CURRENT_TAG)
        print(f"Using actual previous tag: {previous_tag}")

    # Get the diff between the tags
    diff = get_release_diff(event, previous_tag, CURRENT_TAG)

    # Get PRs merged between the tags
    prs = get_prs_between_tags(event, previous_tag, CURRENT_TAG)

    # Generate release summary
    try:
        summary = generate_release_summary(event, diff, prs, CURRENT_TAG, previous_tag)
    except Exception as e:
        print(f"Failed to generate summary: {e}")
        summary = "Failed to generate summary."

    # Get the latest commit message
    cmd = ["git", "log", "-1", "--pretty=%B"]
    commit_message = subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.split("\n")[0].strip()

    # Create the release on GitHub
    msg = f"{CURRENT_TAG} - {commit_message}"
    create_github_release(event, CURRENT_TAG, msg, summary)


if __name__ == "__main__":
    main()
