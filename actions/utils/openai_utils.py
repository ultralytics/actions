# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import os

import requests

from actions.utils.common_utils import check_links_in_string

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-2025-08-07")
SYSTEM_PROMPT_ADDITION = """Guidance:
  - Ultralytics Branding: Use YOLO11, YOLO26, etc., not YOLOv11, YOLOv26 (only older versions like YOLOv10 have a v). Always capitalize "HUB" in "Ultralytics HUB"; use "Ultralytics HUB", not "The Ultralytics HUB". 
  - Avoid Equations: Do not include equations or mathematical notations.
  - Markdown: Reply in Markdown format.
  - Links: Use descriptive anchor text for all URLs.
  - Code: 
    - Provide minimal code examples if helpful.
    - Enclose code in backticks: `pip install ultralytics` for inline code or e.g. ```python for larger code blocks.
    - Think and verify the argument names, methods, class and files used in your code examples for accuracy.
  - Use the "@" symbol to refer to GitHub users, e.g. @glenn-jocher.
  - Tone: Adopt a professional, friendly, and concise tone.
"""


def remove_outer_codeblocks(string):
    """Removes outer code block markers and language identifiers from a string while preserving inner content."""
    string = string.strip()
    if string.startswith("```") and string.endswith("```"):
        # Get everything after first ``` and newline, up to the last ```
        string = string[string.find("\n") + 1 : string.rfind("```")].strip()
    return string


def _to_responses_input(messages: list[dict[str, str]]):
    role_map = {"system": "system", "user": "user", "assistant": "assistant"}
    sys_instructions = ""
    user_input = ""
    for m in messages:
        role = role_map.get(m.get("role"), "user")
        if role == "user" and user_input == "":
            user_input = m.get("content")
        elif role == "system" and sys_instructions == "":
            sys_instructions = m.get("content")

    return sys_instructions, user_input


def get_completion(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),  # strings to remove from response
    temperature: float = 1.0,  # note GPT-5 requires temperature=1.0
    reasoning_effort: str = None,  # reasoning effort for GPT-5 models: minimal, low, medium, high
) -> str:
    """Generates a completion using OpenAI's API based on input messages."""
    assert OPENAI_API_KEY, "OpenAI API key is required."
    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] += "\n\n" + SYSTEM_PROMPT_ADDITION

    content = ""
    max_retries = 2
    for attempt in range(max_retries + 2):  # attempt = [0, 1, 2, 3], 2 random retries before asking for no links
        sys_instructions, user_input = _to_responses_input(messages)

        data = {
            "model": OPENAI_MODEL,
            "input": user_input,
            "temperature": temperature,
        }

        # Adding system instructions if present
        if sys_instructions != "":
            data["instructions"] = sys_instructions

        # Add reasoning_effort for GPT-5 models
        if "gpt-5" in OPENAI_MODEL:
            data["reasoning"] = {"effort": reasoning_effort or "low"}  # Default to low for GPT-5

        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
        content = r.json()["output"][1]["content"][0]["text"].strip()
        content = remove_outer_codeblocks(content)
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


if __name__ == "__main__":
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Explain how to export a YOLO11 model to CoreML."},
    ]
    response = get_completion(messages)
    print(response)
