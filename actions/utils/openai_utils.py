# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import os
import time
from typing import Dict, List

import requests

from actions.utils.common_utils import check_links_in_string

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-2024-11-20")


def get_completion(
    messages: List[Dict[str, str]],
    check_links: bool = True,
    remove: List[str] = (" @giscus[bot]",),  # strings to remove from response
) -> str:
    """Generates a completion using OpenAI's API based on input messages."""
    assert OPENAI_API_KEY, "OpenAI API key is required."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    content = ""
    max_retries = 2
    for attempt in range(max_retries + 2):  # attempt = [0, 1, 2, 3], 2 random retries before asking for no links
        data = {"model": OPENAI_MODEL, "messages": messages, "seed": int(time.time() * 1000)}

        r = requests.post(url, headers=headers, json=data)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        for x in remove:
            content = content.replace(x, "")
        if not check_links or check_links_in_string(content):  # if no checks or checks are passing return response
            return content

        if attempt < max_retries:
            print(f"Attempt {attempt + 1}: Found bad URLs. Retrying with a new random seed.")
        else:
            print("Max retries reached. Updating prompt to exclude links.")
            messages.append({"role": "user", "content": "Please provide a response without any URLs or links in it."})
            check_links = False  # automatically accept the last message

    return content
