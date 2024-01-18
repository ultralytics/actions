import sys

import requests

print(sys.argv)

repo_name = sys.argv[1]
pr_number = sys.argv[2]
github_token = sys.argv[3]

print("CUSTOM PYTHON SCRIPT IS WORKING 1!!")


def get_pr_diff(repo_name, pr_number, github_token):
    """Fetches the diff of a specific PR from a GitHub repository."""
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)

    print(response)
    if response.status_code == 200:
        return response.text
    else:
        return None


if __name__ == "__main__":
    print(repo_name, pr_number, github_token)
    pr_diff = get_pr_diff(repo_name, pr_number, github_token)
    if pr_diff:
        print(pr_diff)
    else:
        print("Failed to fetch PR diff")
