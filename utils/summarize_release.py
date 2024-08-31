# Ultralytics YOLO 🚀, AGPL-3.0 License https://ultralytics.com/license

import os
import subprocess

import requests

# Environment variables
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
PR_NUMBER = os.getenv("PR_NUMBER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
CURRENT_TAG = os.getenv("CURRENT_TAG")
PREVIOUS_TAG = os.getenv("PREVIOUS_TAG")

# OpenAI settings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")  # update as required
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def get_completion(messages: list) -> str:
    """Get completion from OpenAI."""
    assert OPENAI_API_KEY, "OpenAI API key is required."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": OPENAI_MODEL, "messages": messages}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def get_release_diff(repo_name: str, previous_tag: str, latest_tag: str) -> str:
    """Get the diff between two tags."""
    url = f"https://api.github.com/repos/{repo_name}/compare/{previous_tag}...{latest_tag}"
    response = requests.get(url, headers=GITHUB_HEADERS)
    return response.text if response.status_code == 200 else f"Failed to get diff: {response.content}"


def generate_release_summary(diff: str, latest_tag: str) -> str:
    """Generate a summary for the release."""
    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant skilled in software development and technical communication. Your task is to summarize GitHub releases in a way that is detailed, accurate, and understandable to both expert developers and non-expert users. Focus on highlighting the key changes and their impact in simple and intuitive terms.",
        },
        {
            "role": "user",
            "content": f"Summarize the updates made in the '{latest_tag}' tag, focusing on major changes, their purpose, and potential impact. Keep the summary clear and suitable for a broad audience. Add emojis to enliven the summary. Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
            f"## 🌟 Summary (single-line synopsis)\n"
            f"## 📊 Key Changes (bullet points highlighting any major changes)\n"
            f"## 🎯 Purpose & Impact (bullet points explaining any benefits and potential impact to users)\n"
            f"\n\nHere's the release diff:\n\n{diff[:300000]}",
        },
    ]
    return get_completion(messages)


def create_github_release(repo_name: str, tag_name: str, name: str, body: str) -> int:
    """Create a release on GitHub."""
    release_url = f"https://api.github.com/repos/{repo_name}/releases"
    release_data = {"tag_name": tag_name, "name": name, "body": body, "draft": False, "prerelease": False}
    response = requests.post(release_url, headers=GITHUB_HEADERS, json=release_data)
    return response.status_code


def main():
    # Check for required environment variables
    if not all([GITHUB_TOKEN, CURRENT_TAG, PREVIOUS_TAG]):
        raise ValueError("One or more required environment variables are missing.")

    latest_tag = f"v{CURRENT_TAG}"
    previous_tag = f"v{PREVIOUS_TAG}"

    # Get the diff between the tags
    diff = get_release_diff(REPO_NAME, previous_tag, latest_tag)

    # Generate release summary
    try:
        summary = generate_release_summary(diff, latest_tag)
    except Exception as e:
        print(f"Failed to generate summary: {str(e)}")
        summary = "Failed to generate summary."

    # Get the latest commit message
    cmd = ["git", "log", "-1", "--pretty=%B"]
    commit_message = subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.split("\n")[0].strip()

    # Create the release on GitHub
    status_code = create_github_release(REPO_NAME, latest_tag, f"{latest_tag} - {commit_message}", summary)
    if status_code == 201:
        print(f"Successfully created release {latest_tag}")
    else:
        print(f"Failed to create release {latest_tag}. Status code: {status_code}")


if __name__ == "__main__":
    main()
