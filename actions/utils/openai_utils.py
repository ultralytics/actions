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
        string = string[string.find("\n") + 1 : string.rfind("```")].strip()
    return string


def filter_labels(available_labels: dict, current_labels: list = None, is_pr: bool = False) -> dict:
    """Filters labels by removing manually-assigned and mutually exclusive labels."""
    current_labels = current_labels or []
    filtered = available_labels.copy()
    
    # Remove labels that should only be manually assigned
    for label in {"help wanted", "TODO", "research", "non-reproducible", "popular", "invalid", "Stale", "wontfix", "duplicate"}:
        filtered.pop(label, None)
    
    # Remove mutually exclusive labels
    if "bug" in current_labels:
        filtered.pop("question", None)
    elif "question" in current_labels:
        filtered.pop("bug", None)
    
    # Add Alert label if not present
    if "Alert" not in filtered:
        filtered["Alert"] = (
            "Potential spam, abuse, or illegal activity including advertising, unsolicited promotions, malware, "
            "phishing, crypto offers, pirated software or media, free movie downloads, cracks, keygens or any other "
            "content that violates terms of service or legal standards."
        )
    
    return filtered


def get_pr_summary_prompt(repository: str, diff_text: str) -> str:
    """Returns the PR summary generation prompt (used by both PR open and PR update/merge)."""
    if not diff_text:
        diff_text = "**ERROR: DIFF IS EMPTY, THERE ARE ZERO CODE CHANGES IN THIS PR."
    ratio = 3.3  # about 3.3 characters per token
    limit = round(128000 * ratio * 0.5)  # use up to 50% of the 128k context window for prompt
    
    return (
        f"Summarize this '{repository}' PR, focusing on major changes, their purpose, and potential impact. "
        f"Keep the summary clear and concise, suitable for a broad audience. Add emojis to enliven the summary. "
        f"Reply directly with a summary along these example guidelines, though feel free to adjust as appropriate:\n\n"
        f"### 🌟 Summary (single-line synopsis)\n"
        f"### 📊 Key Changes (bullet points highlighting any major changes)\n"
        f"### 🎯 Purpose & Impact (bullet points explaining any benefits and potential impact to users)\n"
        f"\n\nHere's the PR diff:\n\n{diff_text[:limit]}"
    ), len(diff_text) > limit


def get_pr_first_comment_template(repository: str) -> str:
    """Returns the PR first comment template with checklist (used only by unified PR open)."""
    return f"""👋 Hello @username, thank you for submitting an `{repository}` 🚀 PR! To ensure a seamless integration of your work, please review the following checklist:

- ✅ **Define a Purpose**: Clearly explain the purpose of your fix or feature in your PR description, and link to any [relevant issues](https://github.com/{repository}/issues). Ensure your commit messages are clear, concise, and adhere to the project's conventions.
- ✅ **Synchronize with Source**: Confirm your PR is synchronized with the `{repository}` `main` branch. If it's behind, update it by clicking the 'Update branch' button or by running `git pull` and `git merge main` locally.
- ✅ **Ensure CI Checks Pass**: Verify all Ultralytics [Continuous Integration (CI)](https://docs.ultralytics.com/help/CI/) checks are passing. If any checks fail, please address the issues.
- ✅ **Update Documentation**: Update the relevant [documentation](https://docs.ultralytics.com/) for any new or modified features.
- ✅ **Add Tests**: If applicable, include or update tests to cover your changes, and confirm that all tests are passing.
- ✅ **Sign the CLA**: Please ensure you have signed our [Contributor License Agreement](https://docs.ultralytics.com/help/CLA/) if this is your first Ultralytics PR by writing "I have read the CLA Document and I sign the CLA" in a new message.
- ✅ **Minimize Changes**: Limit your changes to the **minimum** necessary for your bug fix or feature addition. _"It is not daily increase but daily decrease, hack away the unessential. The closer to the source, the less wastage there is."_  — Bruce Lee

For more guidance, please refer to our [Contributing Guide](https://docs.ultralytics.com/help/contributing/). Don't hesitate to leave a comment if you have any questions. Thank you for contributing to Ultralytics! 🚀"""


def get_completion(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),
    temperature: float = 1.0,
    reasoning_effort: str = None,
    response_format: dict = None,
) -> str | dict:
    """Generates a completion using OpenAI's Responses API based on input messages."""
    assert OPENAI_API_KEY, "OpenAI API key is required."
    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] += "\n\n" + SYSTEM_PROMPT_ADDITION

    content = ""
    max_retries = 2
    for attempt in range(max_retries + 2):  # attempt = [0, 1, 2, 3], 2 random retries before asking for no links
        data = {"model": OPENAI_MODEL, "input": messages, "store": False, "temperature": temperature}
        if response_format:
            data["response_format"] = response_format
        if "gpt-5" in OPENAI_MODEL:
            data["reasoning"] = {"effort": reasoning_effort or "low"}

        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
        response_data = r.json()

        # Extract text from output array
        content = ""
        for item in response_data.get("output", []):
            if item.get("type") == "message":
                for content_item in item.get("content", []):
                    if content_item.get("type") == "output_text":
                        content += content_item.get("text", "")

        content = content.strip()
        if response_format and response_format.get("type") == "json_object":
            import json
            return json.loads(content)

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


def get_pr_open_response(repository: str, diff_text: str, title: str, body: str, available_labels: dict) -> dict:
    """Generates unified PR response with summary, labels, and first comment in a single API call."""
    filtered_labels = filter_labels(available_labels, is_pr=True)
    labels_str = "\n".join(f"- {name}: {description}" for name, description in filtered_labels.items())
    
    summary_prompt, is_large = get_pr_summary_prompt(repository, diff_text)
    comment_template = get_pr_first_comment_template(repository)

    prompt = f"""You are processing a new GitHub pull request for the {repository.split('/')[-1]} repository.

Generate THREE outputs in a single JSON response:

1. **summary**: {summary_prompt}

2. **labels**: Array of 1-3 most relevant label names. Only use "Alert" with high confidence for inappropriate PRs. Return empty array if no labels relevant.

3. **first_comment**: Customized welcome message adapting the template below:
   - Keep all checklist items and links from template
   - Mention this is automated and an engineer will assist
   - Use a few emojis
   - No sign-off or "best regards"
   - No spaces between bullet points

AVAILABLE LABELS:
{labels_str}

FIRST COMMENT TEMPLATE (adapt as needed, keep all links):
{comment_template}

PR TITLE:
{title}

PR DESCRIPTION:
{body[:16000]}

Return ONLY valid JSON:
{{"summary": "...", "labels": [...], "first_comment": "..."}}"""

    messages = [
        {"role": "system", "content": "You are an Ultralytics AI assistant processing GitHub PRs."},
        {"role": "user", "content": prompt},
    ]
    result = get_completion(messages, temperature=1.0, response_format={"type": "json_object"})
    
    if is_large and "summary" in result:
        result["summary"] = "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + result["summary"]
    
    return result


if __name__ == "__main__":
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Explain how to export a YOLO11 model to CoreML."},
    ]
    response = get_completion(messages)
    print(response)
