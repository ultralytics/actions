# Ultralytics YOLO 🚀, AGPL-3.0 License https://ultralytics.com/license

import os
import re
import subprocess

import requests

# Environment variables
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
CURRENT_TAG = os.getenv("CURRENT_TAG")
PREVIOUS_TAG = os.getenv("PREVIOUS_TAG")

# OpenAI settings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-05-13")  # update as required
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_API_KEY = os.getenv("OPENAI_AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("OPENAI_AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("OPENAI_AZURE_API_VERSION", "2024-05-01-preview")  # update as required


def remove_html_comments(body: str) -> str:
    """Removes HTML comment blocks from the body text."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()


def get_completion(messages: list) -> str:
    """Get completion from OpenAI or Azure OpenAI."""
    if AZURE_API_KEY and AZURE_ENDPOINT:
        url = f"{AZURE_ENDPOINT}/openai/deployments/{OPENAI_MODEL}/chat/completions?api-version={AZURE_API_VERSION}"
        headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
        data = {"messages": messages}
    else:
        assert OPENAI_API_KEY, "OpenAI API key is required."
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "gpt-4o-2024-08-06", "messages": messages}

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def get_release_diff(repo_name: str, previous_tag: str, latest_tag: str) -> str:
    """Get the diff between two tags."""
    url = f"{GITHUB_API_URL}/repos/{repo_name}/compare/{previous_tag}...{latest_tag}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else f"Failed to get diff: {response.content}"


def get_prs_between_tags(repo_name: str, previous_tag: str, latest_tag: str) -> list:
    """Get PRs merged between two tags using the compare API."""
    url = f"{GITHUB_API_URL}/repos/{repo_name}/compare/{previous_tag}...{latest_tag}"
    response = requests.get(url, headers=GITHUB_HEADERS)
    response.raise_for_status()

    data = response.json()
    pr_numbers = set()

    for commit in data["commits"]:
        pr_matches = re.findall(r"#(\d+)", commit["commit"]["message"])
        pr_numbers.update(pr_matches)

    prs = []
    for pr_number in pr_numbers:
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
                }
            )

    return prs


def generate_release_summary(diff: str, prs: list, latest_tag: str, previous_tag: str, repo_name: str) -> str:
    """Generate a summary for the release."""
    pr_summaries = "\n".join([f"PR #{pr['number']}: {pr['title']} by @{pr['author']}\n{pr['body'][:1000]}..." for pr in prs])

    current_pr = prs[0] if prs else None
    current_pr_summary = (
        f"Current PR #{current_pr['number']}: {current_pr['title']} by @{current_pr['author']}\n{current_pr['body'][:1000]}..."
        if current_pr
        else "No current PR found."
    )

    whats_changed = "\n".join([f"* {pr['title']} by @{pr['author']} in {pr['html_url']}" for pr in prs])
    full_changelog = f"https://github.com/{repo_name}/compare/{previous_tag}...{latest_tag}"

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
    return (
        get_completion(messages) + f"\n\n## What's Changed\n{whats_changed}\n\n**Full Changelog**: {full_changelog}\n"
    )


def create_github_release(repo_name: str, tag_name: str, name: str, body: str) -> int:
    """Create a release on GitHub."""
    url = f"{GITHUB_API_URL}/repos/{repo_name}/releases"
    data = {"tag_name": tag_name, "name": name, "body": body, "draft": False, "prerelease": False}
    response = requests.post(url, headers=GITHUB_HEADERS, json=data)
    return response.status_code


def get_previous_tag() -> str:
    """Get the previous tag from git tags."""
    cmd = ["git", "describe", "--tags", "--abbrev=0", "--exclude", CURRENT_TAG]
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.strip()
    except subprocess.CalledProcessError:
        print("Failed to get previous tag from git. Using previous commit.")
        return "HEAD~1"


def main():
    # Check for required environment variables
    if not all([GITHUB_TOKEN, CURRENT_TAG]):
        raise ValueError("One or more required environment variables are missing.")

    previous_tag = PREVIOUS_TAG or get_previous_tag()

    # Get the diff between the tags
    diff = get_release_diff(REPO_NAME, previous_tag, CURRENT_TAG)

    # Get PRs merged between the tags
    prs = get_prs_between_tags(REPO_NAME, previous_tag, CURRENT_TAG)

    # Generate release summary
    try:
        summary = generate_release_summary(diff, prs, CURRENT_TAG, previous_tag, REPO_NAME)
    except Exception as e:
        print(f"Failed to generate summary: {str(e)}")
        summary = "Failed to generate summary."

    # Get the latest commit message
    cmd = ["git", "log", "-1", "--pretty=%B"]
    commit_message = subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.split("\n")[0].strip()

    # Create the release on GitHub
    status_code = create_github_release(REPO_NAME, CURRENT_TAG, f"{CURRENT_TAG} - {commit_message}", summary)
    if status_code == 201:
        print(f"Successfully created release {CURRENT_TAG}")
    else:
        print(f"Failed to create release {CURRENT_TAG}. Status code: {status_code}")


if __name__ == "__main__":
    main()
