# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import os
import re
import time

import requests

from actions.utils.common_utils import check_links_in_string, filter_diff_text, format_skipped_files_note

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2-2025-12-11")
MAX_PROMPT_CHARS = round(128000 * 3.3 * 0.5)  # Max characters for prompt (50% of 128k context)
MODEL_COSTS = {
    "gpt-5-codex": (1.25, 10.00),
    "gpt-5.1-codex": (1.25, 10.00),
    "gpt-5.1-2025-11-13": (1.25, 10.00),
    "gpt-5.2-2025-12-11": (1.75, 14.00),
    "gpt-5-nano-2025-08-07": (0.05, 0.40),
    "gpt-5-mini-2025-08-07": (0.25, 2.00),
}
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
_CITATION_PATTERN = re.compile(
    r"[\uE000-\uF8FF]*\bcite[\uE000-\uF8FF]*(turn\d+(?:search|view)\d+|[\w\d]+)[\uE000-\uF8FF]*"
)


def sanitize_ai_text(s: str) -> str:
    """Strip private-use citation tokens (for example, ``cite...`` markers)."""
    return _CITATION_PATTERN.sub("", s) if s else ""


def remove_outer_codeblocks(string):
    """Removes outer code block markers and language identifiers from a string while preserving inner content."""
    string = string.strip()
    if string.startswith("```") and string.endswith("```"):
        string = string[string.find("\n") + 1 : string.rfind("```")].strip()
    return string


def filter_labels(available_labels: dict, current_labels: list | None = None, is_pr: bool = False) -> dict:
    """Filters labels by removing manually-assigned and mutually exclusive labels."""
    current_labels = current_labels or []
    filtered = available_labels.copy()

    for label in {
        "help wanted",
        "TODO",
        "research",
        "non-reproducible",
        "popular",
        "invalid",
        "Stale",
        "wontfix",
        "duplicate",
    }:
        filtered.pop(label, None)

    if "bug" in current_labels:
        filtered.pop("question", None)
    elif "question" in current_labels:
        filtered.pop("bug", None)

    if "Alert" not in filtered:
        filtered["Alert"] = (
            "Potential spam, abuse, or illegal activity including advertising, unsolicited promotions, malware, "
            "phishing, crypto offers, pirated software or media, free movie downloads, cracks, keygens or any other "
            "content that violates terms of service or legal standards."
        )

    return filtered


def get_pr_summary_guidelines() -> str:
    """Returns PR summary formatting guidelines (used by both unified PR open and PR update/merge)."""
    return """Summarize this PR, focusing on major changes, their purpose, and potential impact. Keep the summary clear and concise, suitable for a broad audience. Add emojis to enliven the summary. Your response must include all 3 sections below with their markdown headers:

### 🌟 Summary
(single-line synopsis)

### 📊 Key Changes
- (bullet points highlighting major changes)

### 🎯 Purpose & Impact
- (bullet points explaining benefits and potential impact to users)"""


def get_pr_summary_prompt(repository: str, diff_text: str) -> tuple[str, bool, list[str]]:
    """Returns the complete PR summary generation prompt with filtered diff (used by PR update/merge)."""
    filtered_diff, skipped_files = filter_diff_text(diff_text)
    prompt = f"{get_pr_summary_guidelines()}\n\nRepository: '{repository}'\n\nHere's the PR diff:\n\n{filtered_diff[:MAX_PROMPT_CHARS]}"
    prompt += format_skipped_files_note(skipped_files)
    return prompt, len(filtered_diff) > MAX_PROMPT_CHARS, skipped_files


def get_pr_first_comment_template(repository: str, username: str) -> str:
    """Returns the PR first comment template with checklist (used only by unified PR open)."""
    return f"""👋 Hello @{username}, thank you for submitting a `{repository}` 🚀 PR! To ensure a seamless integration of your work, please review the following checklist:

- ✅ **Define a Purpose**: Clearly explain the purpose of your fix or feature in your PR description, and link to any [relevant issues](https://github.com/{repository}/issues). Ensure your commit messages are clear, concise, and adhere to the project's conventions.
- ✅ **Synchronize with Source**: Confirm your PR is synchronized with the `{repository}` `main` branch. If it's behind, update it by clicking the 'Update branch' button or by running `git pull` and `git merge main` locally.
- ✅ **Ensure CI Checks Pass**: Verify all Ultralytics [Continuous Integration (CI)](https://docs.ultralytics.com/help/CI/) checks are passing. If any checks fail, please address the issues.
- ✅ **Update Documentation**: Update the relevant [documentation](https://docs.ultralytics.com/) for any new or modified features.
- ✅ **Add Tests**: If applicable, include or update tests to cover your changes, and confirm that all tests are passing.
- ✅ **Sign the CLA**: Please ensure you have signed our [Contributor License Agreement](https://docs.ultralytics.com/help/CLA/) if this is your first Ultralytics PR by writing "I have read the CLA Document and I sign the CLA" in a new message.
- ✅ **Minimize Changes**: Limit your changes to the **minimum** necessary for your bug fix or feature addition. _"It is not daily increase but daily decrease, hack away the unessential. The closer to the source, the less wastage there is."_  — Bruce Lee

For more guidance, please refer to our [Contributing Guide](https://docs.ultralytics.com/help/contributing/). Don't hesitate to leave a comment if you have any questions. Thank you for contributing to Ultralytics! 🚀"""


def get_response(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),
    temperature: float = 1.0,
    reasoning_effort: str | None = None,
    text_format: dict | None = None,
    model: str = OPENAI_MODEL,
    tools: list[dict] | None = None,
) -> str | dict:
    """Generates a completion using OpenAI's Responses API with retry logic."""
    assert OPENAI_API_KEY, "OpenAI API key is required."
    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] += "\n\n" + SYSTEM_PROMPT_ADDITION

    for attempt in range(3):
        data = {"model": model, "input": messages, "store": False, "temperature": temperature}
        if "gpt-5" in model:
            data["reasoning"] = {"effort": reasoning_effort or "low"}
        if text_format:
            data["text"] = text_format
        if tools:
            data["tools"] = tools

        try:
            r = requests.post(url, json=data, headers=headers, timeout=(30, 900))
            elapsed = r.elapsed.total_seconds()
            success = r.status_code == 200
            print(f"{'✓' if success else '✗'} POST {url} → {r.status_code} ({elapsed:.1f}s)")

            # Retry server errors
            if attempt < 2 and r.status_code >= 500:
                print(f"Retrying {r.status_code} in {2**attempt}s (attempt {attempt + 1}/3)...")
                time.sleep(2**attempt)
                continue

            if r.status_code >= 400:
                error_body = r.text
                print(f"API Error {r.status_code}: {error_body}")
                r.reason = f"{r.reason}\n{error_body}"  # Add error body to exception message

            r.raise_for_status()

            # Parse response
            response_json = r.json()
            content = ""
            for item in response_json.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            content += c.get("text") or ""
            content = content.strip()

            # Extract and print token usage
            if usage := response_json.get("usage"):
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                thinking_tokens = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)

                # Calculate cost
                costs = MODEL_COSTS.get(model, (0.0, 0.0))
                cost = (input_tokens * costs[0] + output_tokens * costs[1]) / 1e6

                # Format summary
                token_str = f"{input_tokens}→{output_tokens - thinking_tokens}"
                if thinking_tokens:
                    token_str += f" (+{thinking_tokens} thinking)"
                print(f"{model} ({token_str} = {input_tokens + output_tokens} tokens, ${cost:.5f}, {elapsed:.1f}s)")

            if text_format and text_format.get("format", {}).get("type") in ["json_object", "json_schema"]:
                return json.loads(content)

            content = remove_outer_codeblocks(content)
            for x in remove:
                content = content.replace(x, "")

            # Retry on bad links
            if attempt < 2 and check_links and not check_links_in_string(content):
                print("Bad URLs detected, retrying")
                continue

            return content

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, json.JSONDecodeError) as e:
            if attempt < 2:
                print(f"Retrying {e.__class__.__name__} in {2**attempt}s (attempt {attempt + 1}/3)...")
                time.sleep(2**attempt)
                continue
            raise
        except requests.exceptions.HTTPError:  # 4xx errors
            raise

    return content


def get_pr_open_response(repository: str, diff_text: str, title: str, username: str, available_labels: dict) -> dict:
    """Generates unified PR response with summary, labels, and first comment in a single API call."""
    filtered_diff, skipped_files = filter_diff_text(diff_text)
    is_large = len(filtered_diff) > MAX_PROMPT_CHARS

    filtered_labels = filter_labels(available_labels, is_pr=True)
    labels_str = "\n".join(f"- {name}: {description}" for name, description in filtered_labels.items())

    prompt = f"""You are processing a new GitHub PR by @{username} for the {repository} repository.

Generate 3 outputs in a single JSON response for the PR titled '{title}' with the following diff:
{filtered_diff[:MAX_PROMPT_CHARS]}{format_skipped_files_note(skipped_files)}


--- FIRST JSON OUTPUT (PR SUMMARY) ---
{get_pr_summary_guidelines()}

--- SECOND JSON OUTPUT (PR LABELS) ---
Array of 1-3 most relevant label names. Only use "Alert" with high confidence for inappropriate PRs. Return empty array if no labels relevant. Available labels:
{labels_str}

--- THIRD OUTPUT (PR FIRST COMMENT) ---
Customized welcome message adapting the template below:
- INCLUDE ALL LINKS AND INSTRUCTIONS from the template below, customized as appropriate
- Keep all checklist items and links from template
- Only link to files or URLs in the template below, do not add external links
- Mention this is automated and an engineer will assist
- Use a few emojis
- No sign-off or "best regards"
- No spaces between bullet points

Example comment template (adapt as needed, keep all links):
{get_pr_first_comment_template(repository, username)}"""

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "PR summary with emoji sections"},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Array of label names"},
            "first_comment": {"type": "string", "description": "Welcome comment with checklist"},
        },
        "required": ["summary", "labels", "first_comment"],
        "additionalProperties": False,
    }

    messages = [
        {"role": "system", "content": "You are an Ultralytics AI assistant processing GitHub PRs."},
        {"role": "user", "content": prompt},
    ]
    result = get_response(
        messages,
        temperature=1.0,
        text_format={"format": {"type": "json_schema", "name": "pr_open_response", "strict": True, "schema": schema}},
    )
    if is_large and "summary" in result:
        result["summary"] = (
            "**WARNING ⚠️** this PR is very large, summary may not cover all changes.\n\n" + result["summary"]
        )
    result["skipped_files"] = skipped_files
    return result


if __name__ == "__main__":
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Explain how to export a YOLO11 model to CoreML."},
    ]
    response = get_response(messages)
    print(response)
