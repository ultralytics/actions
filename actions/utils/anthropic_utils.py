# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import os
import time

import requests

from actions.utils.common_utils import check_links_in_string
from actions.utils.openai_utils import SYSTEM_PROMPT_ADDITION, remove_outer_codeblocks

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
MODEL_COSTS = {"claude-sonnet-4-5-20250929": (3.00, 15.00)}
THINKING_BUDGET = {"low": 1024, "medium": 4096, "high": 16384}
WEB_SEARCH_COST_PER_1K = 10.00  # $10 per 1,000 searches


def convert_openai_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool format to Anthropic tool format."""
    anthropic_tools = []
    for tool in tools:
        tool_type = tool.get("type")
        if tool_type == "web_search":
            anthropic_tool = {"type": "web_search_20250305", "name": "web_search"}
            if filters := tool.get("filters"):
                if allowed := filters.get("allowed_domains"):
                    anthropic_tool["allowed_domains"] = allowed
                if blocked := filters.get("blocked_domains"):
                    anthropic_tool["blocked_domains"] = blocked
            anthropic_tools.append(anthropic_tool)
        else:
            print(f"WARNING ⚠️ Tool type '{tool_type}' not supported for Anthropic API, skipping")
    return anthropic_tools


def get_response(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),
    temperature: float = 1.0,
    reasoning_effort: str | None = None,  # maps to thinking.budget_tokens
    text_format: dict | None = None,
    model: str = ANTHROPIC_MODEL,
    tools: list[dict] | None = None,  # ignored, for API compat
) -> str | dict:
    """Generate completion using Anthropic Messages API with retry logic."""
    assert ANTHROPIC_API_KEY, "Anthropic API key is required."
    anthropic_tools = convert_openai_tools_to_anthropic(tools) if tools else None
    url = "https://api.anthropic.com/v1/messages"

    # Extract system prompt
    system_content, claude_messages = None, []
    for msg in messages:
        if msg.get("role") == "system":
            system_content = (
                (msg["content"] + "\n\n" + SYSTEM_PROMPT_ADDITION) if msg.get("content") else SYSTEM_PROMPT_ADDITION
            )
        else:
            claude_messages.append(msg)

    # Convert text_format to output_format (beta)
    output_format = None
    if text_format and text_format.get("format", {}).get("type") == "json_schema":
        output_format = {"type": "json_schema", "schema": text_format["format"]["schema"]}

    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    beta_features = []
    if output_format:
        beta_features.append("structured-outputs-2025-11-13")
    if reasoning_effort:
        beta_features.append("interleaved-thinking-2025-05-14")
    if beta_features:
        headers["anthropic-beta"] = ",".join(beta_features)

    for attempt in range(3):
        data = {"model": model, "max_tokens": 8192, "messages": claude_messages, "temperature": temperature}
        if system_content:
            data["system"] = system_content
        if output_format:
            data["output_format"] = output_format
        if reasoning_effort:
            data["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET.get(reasoning_effort, 1024)}
        if anthropic_tools:
            data["tools"] = anthropic_tools

        try:
            r = requests.post(url, json=data, headers=headers, timeout=(30, 900))
            elapsed = r.elapsed.total_seconds()
            print(f"{'✓' if r.status_code == 200 else '✗'} POST {url} → {r.status_code} ({elapsed:.1f}s)")

            if attempt < 2 and r.status_code >= 500:
                print(f"Retrying {r.status_code} in {2**attempt}s (attempt {attempt + 1}/3)...")
                time.sleep(2**attempt)
                continue
            if r.status_code >= 400:
                print(f"API Error {r.status_code}: {r.text}")
                r.reason = f"{r.reason}\n{r.text}"
            r.raise_for_status()

            response_json = r.json()
            content = "".join(
                b.get("text", "") for b in response_json.get("content", []) if b.get("type") == "text"
            ).strip()

            if usage := response_json.get("usage"):
                # Note: output_tokens includes thinking tokens. Anthropic doesn't provide separate thinking token counts.
                # See https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking#pricing
                input_tokens, output_tokens = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
                costs = MODEL_COSTS.get(model, (0.0, 0.0))
                cost = (input_tokens * costs[0] + output_tokens * costs[1]) / 1e6
                # Add web search cost if applicable
                if server_tool_use := usage.get("server_tool_use"):
                    web_searches = server_tool_use.get("web_search_requests", 0)
                    cost += web_searches * WEB_SEARCH_COST_PER_1K / 1000
                print(
                    f"{model} ({input_tokens}→{output_tokens} = {input_tokens + output_tokens} tokens, ${cost:.5f}, {elapsed:.1f}s)"
                )

            if output_format:
                return json.loads(content)

            content = remove_outer_codeblocks(content)
            for x in remove:
                content = content.replace(x, "")
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
        except requests.exceptions.HTTPError:
            raise
    return content
