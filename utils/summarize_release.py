# Ultralytics YOLO 🚀, AGPL-3.0 License https://ultralytics.com/license

import json
import os
import subprocess

import openai
import requests

# Environment variables
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
PR_NUMBER = os.getenv("PR_NUMBER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
GITHUB_API_URL = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
CURRENT_TAG = os.getenv('CURRENT_TAG')
PREVIOUS_TAG = os.getenv('PREVIOUS_TAG')

# OpenAI settings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")  # update as required
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Check for required environment variables
if not all([OPENAI_API_KEY, GITHUB_TOKEN, CURRENT_TAG, PREVIOUS_TAG]):
    raise ValueError("One or more required environment variables are missing.")

latest_tag = f"v{CURRENT_TAG}"
previous_tag = f"v{PREVIOUS_TAG}"

# Get the diff between the tags
url = f"https://api.github.com/repos/{REPO_NAME}/compare/{previous_tag}...{latest_tag}"
response = requests.get(url, headers=GITHUB_HEADERS)
diff = response.text if response.status_code == 200 else f"Failed to get diff: {response.content}"

# Get summary
messages = [
    {
        "role": "system",
        "content": "You are an Ultralytics AI assistant skilled in software development and technical communication. Your task is to summarize GitHub releases in a way that is detailed, accurate, and understandable to both expert developers and non-expert users. Focus on highlighting the key changes and their impact in simple and intuitive terms."
    },
    {
        "role": "user",
        "content": f"Summarize the updates made in the '{latest_tag}' tag, focusing on major changes, their purpose, and potential impact. Keep the summary clear and suitable for a broad audience. Add emojis to enliven the summary. Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
                   f"## 🌟 Summary (single-line synopsis)\n"
                   f"## 📊 Key Changes (bullet points highlighting any major changes)\n"
                   f"## 🎯 Purpose & Impact (bullet points explaining any benefits and potential impact to users)\n"
                   f"\n\nHere's the release diff:\n\n{diff[:300000]}",
    }
]
client = openai.OpenAI(api_key=OPENAI_API_KEY)
completion = client.chat.completions.create(model="gpt-4o-2024-08-06", messages=messages)
summary = completion.choices[0].message.content.strip()

# Get the latest commit message
cmd = ['git', 'log', '-1', '--pretty=%B']
commit_message = subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.split("\n")[0].strip()

# Prepare release data
release = {
    'tag_name': latest_tag,
    'name': f"{latest_tag} - {commit_message}",
    'body': summary,
    'draft': False,
    'prerelease': False
}

# Create the release on GitHub
release_url = f"https://api.github.com/repos/{REPO_NAME}/releases"
release_response = requests.post(release_url, headers=GITHUB_HEADERS, data=json.dumps(release))
if release_response.status_code == 201:
    print(f'Successfully created release {latest_tag}')
else:
    print(f'Failed to create release {latest_tag}: {release_response.content}')
