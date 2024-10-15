import os
import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def get_pr_diff(repo_name: str, pr_number: int) -> str:
    url = f"{GITHUB_API_URL}/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}
    r = requests.get(url, headers=headers)
    return r.text if r.status_code == 200 else ""

def get_github_data(repo_name: str, endpoint: str) -> dict:
    r = requests.get(f"{GITHUB_API_URL}/repos/{repo_name}/{endpoint}", headers=GITHUB_HEADERS)
    r.raise_for_status()
    return r.json()

def graphql_request(query: str, variables: dict = None) -> dict:
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v4+json",
    }
    r = requests.post(f"{GITHUB_API_URL}/graphql", json={"query": query, "variables": variables}, headers=headers)
    r.raise_for_status()
    result = r.json()
    success = "data" in result and not result.get("errors")
    print(f"{'Successful' if success else 'Fail'} discussion GraphQL request: {result.get('errors', 'No errors')}")
    return result
