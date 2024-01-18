import os

print("CUSTOM PYTHON SCRIPT IS WORKING 1!!")

import requests

print("CUSTOM PYTHON SCRIPT IS WORKING 2!!")


def get_pr_diff(repo_name, pr_number, github_token):
    """Fetches the diff of a specific PR from a GitHub repository."""
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        return None


# Example usage
repo_name = os.environ["REPO_NAME"]
pr_number = os.environ["PR_NUMBER"]
github_token = os.environ["GITHUB_TOKEN"]
pr_diff = get_pr_diff(repo_name, pr_number, github_token)
if pr_diff:
    print(pr_diff)
else:
    print("Failed to fetch PR diff")
