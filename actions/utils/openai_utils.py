# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import os

import requests

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def get_completion(messages: list) -> str:
    """Generates a completion using OpenAI's API based on input messages."""
    assert OPENAI_API_KEY, "OpenAI API key is required."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": OPENAI_MODEL, "messages": messages}

    r = requests.post(url, headers=headers, json=data)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    remove = [" @giscus[bot]"]
    for x in remove:
        content = content.replace(x, "")
    return content
