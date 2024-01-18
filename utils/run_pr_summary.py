import os

import requests

REPO_NAME = os.getenv("REPO_NAME")
PR_NUMBER = os.getenv("PR_NUMBER")
github_token = os.getenv("GITHUB_TOKEN")


def get_pr_diff():
    """Fetches the diff of a specific PR from a GitHub repository."""
    url = f"https://api.github.com/repos/{REPO_NAME}/pulls/{PR_NUMBER}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else ""


if __name__ == "__main__":
    pr_diff = get_pr_diff()
