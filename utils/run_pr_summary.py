import os

import requests


def get_pr_diff(repo_name, pr_number, github_token):
    """Fetches the diff of a specific PR from a GitHub repository."""
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else ""


if __name__ == "__main__":
    repo_name = os.getenv("REPO_NAME")
    pr_number = os.getenv("PR_NUMBER")
    github_token = os.getenv("GITHUB_TOKEN")

    print(repo_name, pr_number, github_token)
    pr_diff = get_pr_diff(repo_name, pr_number, github_token)
    if pr_diff:
        print(pr_diff)
    else:
        print("Failed to fetch PR diff")
