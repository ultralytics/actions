import os

import requests
from openai import OpenAI, AzureOpenAI

REPO_NAME = os.getenv("REPO_NAME")
PR_NUMBER = os.getenv("PR_NUMBER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_AZURE_API_KEY = os.getenv("OPENAI_AZURE_API_KEY")
OPENAI_AZURE_ENDPOINT = os.getenv("OPENAI_AZURE_ENDPOINT")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_MODEL_TOKENS = 128000
SUMMARY_START = (
    "## 🛠️ PR Summary\n\n<sub>Made with ❤️ by [Ultralytics Actions](https://github.com/ultralytics/actions)<sub>\n\n"
)


def openai_client(azure=OPENAI_AZURE_ENDPOINT and OPENAI_AZURE_API_KEY):
    """Returns OpenAI client instance."""
    return (
        AzureOpenAI(
            api_key=OPENAI_AZURE_API_KEY, api_version="2023-09-01-preview", azure_endpoint=OPENAI_AZURE_ENDPOINT
        )
        if azure
        else OpenAI(api_key=OPENAI_API_KEY)
    )


def get_pr_diff(repo_name, pr_number):
    """Fetches the diff of a specific PR from a GitHub repository."""
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else ""


def generate_pr_summary(repo_name, pr_title, diff_text):
    """Generates a professionally written yet accessible summary of a PR using OpenAI's API."""
    if not diff_text:
        diff_text = "**ERROR: DIFF IS EMPTY, THERE ARE ZERO CODE CHANGES IN THIS PR."
    ratio = 3.3  # about 3.3 characters per token
    limit = round(OPENAI_MODEL_TOKENS * ratio * 0.7)  # use up to 70% of the context window
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
    response = openai_client().chat.completions.create(model=OPENAI_MODEL, messages=messages).choices[0]
    reply = response.message.content.strip()
    if len(diff_text) > limit:
        return SUMMARY_START + "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + reply
    else:
        return SUMMARY_START + reply


def update_pr_description(repo_name, pr_number, new_summary):
    """Updates the original PR description with a new summary, replacing an existing summary if found."""
    # Fetch the current PR description
    pr_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
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


if __name__ == "__main__":
    # Fetch PR details
    pr_diff = get_pr_diff(REPO_NAME, PR_NUMBER)

    # Generate PR summary
    summary = generate_pr_summary(REPO_NAME, PR_NUMBER, pr_diff)

    # Update PR description
    status_code = update_pr_description(REPO_NAME, PR_NUMBER, summary)
    if status_code == 200:
        print("PR description updated successfully.")
    else:
        print(f"Failed to update PR description. Status code: {status_code}")
