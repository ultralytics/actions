# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import requests

from actions.utils.common_utils import check_links_in_string, filter_diff_text, format_skipped_files_note

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("MODEL")  # Auto-detected from API keys if not set
REVIEW_MODEL = os.getenv("REVIEW_MODEL")  # Optional override for PR reviews
MAX_PROMPT_CHARS = round(128000 * 3.3 * 0.5)  # deliberate COST ceiling, not a context limit; agent tools read the rest
WEB_SEARCH_CALL_COST = 0.01  # $10 per 1K calls

# Default models (single source of truth)
OPENAI_MODEL_DEFAULT = "gpt-5.6-luna"
ANTHROPIC_MODEL_DEFAULT = "claude-sonnet-4-6"
PR_REVIEW_MODEL_DEFAULT = "gpt-5.6-terra"

MODEL_COSTS = {  # (input, output) per 1M tokens
    # OpenAI models
    "gpt-5-codex": (1.25, 10.00),
    "gpt-5.1-codex": (1.25, 10.00),
    "gpt-5.1-2025-11-13": (1.25, 10.00),
    "gpt-5.2-2025-12-11": (1.75, 14.00),
    "gpt-5.2-codex": (1.75, 14.00),
    "gpt-5.3-codex": (1.75, 14.00),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.6-sol": (5.00, 30.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5-nano-2025-08-07": (0.05, 0.40),
    "gpt-5-mini-2025-08-07": (0.25, 2.00),
    # Anthropic Claude models
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-opus-4-5-20251101": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),  # introductory pricing through 2026-08-31, then (3.00, 15.00)
    "claude-opus-4-8": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
}
SYSTEM_PROMPT_ADDITION = """Guidance:
  - Ultralytics Branding: Use YOLO11, YOLO26, etc., not YOLOv11, YOLOv26 (only older versions like YOLOv10 have a v).
  - YOLO26: Latest stable and recommended Ultralytics model for all use cases. See https://docs.ultralytics.com/models/yolo26/ for details.
  - Ultralytics Platform: The simplest way to annotate datasets, train and deploy YOLO models at https://platform.ultralytics.com.
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
    """Filters labels by removing manually-assigned and mutually exclusive labels, adding an Alert label if absent."""
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
    return """Summarize this PR, focusing on major changes, their purpose, and potential impact. Keep the summary clear and concise, suitable for a broad audience. Add emojis to enliven the summary. Your response must include all 3 sections below with their H3 Markdown headers (do not use H1 or H2 headers):

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
- ✅ **Ensure CI Checks Pass**: Verify all Ultralytics [Continuous Integration (CI)](https://docs.ultralytics.com/help/CI) checks are passing. If any checks fail, please address the issues.
- ✅ **Update Documentation**: Update the relevant [documentation](https://docs.ultralytics.com/) for any new or modified features.
- ✅ **Add Tests**: If applicable, include or update tests to cover your changes, and confirm that all tests are passing.
- ✅ **Sign the CLA**: Please ensure you have signed our [Contributor License Agreement](https://docs.ultralytics.com/help/CLA) if this is your first Ultralytics PR by writing "I have read the CLA Document and I sign the CLA" in a new message.
- ✅ **Minimize Changes**: Limit your changes to the **minimum** necessary for your bug fix or feature addition. _"It is not daily increase but daily decrease, hack away the unessential. The closer to the source, the less wastage there is."_  — Bruce Lee

For more guidance, please refer to our [Contributing Guide](https://docs.ultralytics.com/help/contributing). Don't hesitate to leave a comment if you have any questions. Thank you for contributing to Ultralytics! 🚀"""


def _is_anthropic_model(model: str) -> bool:
    """Check if the model is an Anthropic model."""
    return model.startswith("claude")


def _get_default_model() -> str:
    """Get default model based on available API keys."""
    if MODEL:
        return MODEL
    if ANTHROPIC_API_KEY:
        return ANTHROPIC_MODEL_DEFAULT
    return OPENAI_MODEL_DEFAULT


def get_review_model() -> str:
    """Get model for PR reviews, using REVIEW_MODEL if set, otherwise PR_REVIEW_MODEL_DEFAULT."""
    return REVIEW_MODEL or PR_REVIEW_MODEL_DEFAULT


def _poll_openai_response(response_json: dict, headers: dict, timeout: int = 900) -> dict:
    """Poll a background OpenAI response until it reaches a terminal state."""
    response_id = response_json.get("id")
    deadline = time.time() + timeout
    while response_id and response_json.get("status") in {"queued", "in_progress"}:
        if time.time() > deadline:
            raise TimeoutError(f"OpenAI background response {response_id} did not complete within {timeout}s")
        print(f"OpenAI response {response_id} is {response_json.get('status')}; polling...")
        time.sleep(2)
        try:
            r = requests.get(f"https://api.openai.com/v1/responses/{response_id}", headers=headers, timeout=(30, 60))
            if r.status_code >= 500 or r.status_code == 429:  # transient; the deadline above bounds the loop
                print(f"OpenAI poll got {r.status_code}; continuing...")
                continue
            r.raise_for_status()
            response_json = r.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, json.JSONDecodeError) as e:
            print(f"OpenAI poll failed with {e.__class__.__name__}; continuing...")

    if response_id and response_json.get("status") != "completed":
        error = response_json.get("error") or response_json.get("incomplete_details") or response_json.get("status")
        raise RuntimeError(f"OpenAI background response {response_id} ended with {error}")
    return response_json


def _openai_response_text(response_json: dict) -> str:
    """Extract assistant text from an OpenAI Responses API response."""
    content = ""
    for item in response_json.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    content += c.get("text") or ""
    return content.strip()


def _response_tool_calls(output_items: list[dict]) -> list[str]:
    """Name Responses API tool-call output items, including hosted tools (e.g. web_search_call -> web_search)."""
    return [
        item.get("name") or (item.get("type") or "")[: -len("_call")]  # removesuffix needs py3.9+, repo floor is 3.8
        for item in output_items
        if (item.get("type") or "").endswith("_call")
    ]


def _add_openai_usage(total_usage: dict | None, response_json: dict) -> dict | None:
    """Add one Responses API usage block into a cumulative usage block."""
    usage = response_json.get("usage")
    if not usage:
        return total_usage

    total_usage = total_usage or {
        "input_tokens": 0,
        "output_tokens": 0,
        "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }
    total_usage["input_tokens"] += usage.get("input_tokens", 0)
    total_usage["output_tokens"] += usage.get("output_tokens", 0)
    total_usage["input_tokens_details"]["cached_tokens"] += (usage.get("input_tokens_details") or {}).get(
        "cached_tokens", 0
    )
    total_usage["input_tokens_details"]["cache_write_tokens"] += (usage.get("input_tokens_details") or {}).get(
        "cache_write_tokens", 0
    )
    total_usage["output_tokens_details"]["reasoning_tokens"] += (usage.get("output_tokens_details") or {}).get(
        "reasoning_tokens", 0
    )
    return total_usage


def _normalize_usage_tokens(usage: dict) -> tuple[int, int, int]:
    """Return input, cache-read, and cache-write tokens for OpenAI Responses or Anthropic Messages usage shapes.

    Anthropic reports cache reads/writes outside input_tokens, so both fold back into the input total and reads count as
    cached — the same normalization ultralytics/assistant applies, keeping cross-repo telemetry identical.
    """
    cache_read = usage.get("cache_read_input_tokens", 0)
    input_tokens = usage.get("input_tokens", 0) + cache_read + usage.get("cache_creation_input_tokens", 0)
    details = usage.get("input_tokens_details") or {}
    cached_tokens = details.get("cached_tokens", 0) or cache_read
    cache_write_tokens = details.get("cache_write_tokens", 0)
    return input_tokens, cached_tokens, cache_write_tokens


def _openai_usage_cost(usage: dict, model: str) -> float:
    """Compute billed USD cost including GPT-5.6 cache-write and long-context rates."""
    costs = MODEL_COSTS.get(model, (0.0, 0.0))
    input_tokens, cached_tokens, cache_write_tokens = _normalize_usage_tokens(usage)
    cache_write_premium = cache_write_tokens * 0.25 if model.startswith("gpt-5.6-") else 0
    billed_input = input_tokens - cached_tokens * 0.9 + cache_write_premium
    long_context = model.startswith("gpt-5.6-") and input_tokens > 272000
    return (
        billed_input * costs[0] * (2 if long_context else 1)
        + usage.get("output_tokens", 0) * costs[1] * (1.5 if long_context else 1)
    ) / 1e6


def _format_tool_calls(calls: list[str]) -> str:
    """Format tool calls with per-type counts: '5 tools (2 lookup_value, 3 web_search)'."""
    counts = {}
    for name in calls:
        counts[name] = counts.get(name, 0) + 1
    types = ", ".join(f"{n} {name}" if n > 1 else name for name, n in counts.items())
    return f"{len(calls)} tools" + (f" ({types})" if calls else "")


def _print_openai_usage(
    response_json: dict, model: str, elapsed: float, metadata: str = "", billed_cost: float | None = None
) -> None:
    """Print token/cost telemetry: 'model: 136036→289 tokens (72% cached, 31 thinking), $0.69, 8.9s'."""
    if usage := response_json.get("usage"):
        input_tokens, cached_tokens, _ = _normalize_usage_tokens(usage)
        output_tokens = usage.get("output_tokens", 0)  # includes thinking, noted in the parenthetical
        thinking_tokens = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
        cost = _openai_usage_cost(usage, model) if billed_cost is None else billed_cost
        notes = []
        if cached_tokens:
            notes.append(f"{round(100 * cached_tokens / input_tokens)}% cached")
        if thinking_tokens:
            notes.append(f"{thinking_tokens} thinking")
        note_str = f" ({', '.join(notes)})" if notes else ""
        metadata = f", {metadata}" if metadata else ""
        cost_str = f"${cost:.2f}" if cost == 0 or cost >= 0.01 else f"${cost:.5f}"  # match ultralytics/assistant
        print(f"{model}: {input_tokens}→{output_tokens} tokens{note_str}, {cost_str}, {elapsed:.1f}s{metadata}")


def _post_openai_response(
    data: dict, headers: dict, retries: int, request_timeout: tuple[int, int]
) -> tuple[dict, float]:
    """Post to the Responses API with the same transient retry policy as get_response()."""
    url = "https://api.openai.com/v1/responses"
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=data, headers=headers, timeout=request_timeout)
            elapsed = r.elapsed.total_seconds()
            success = r.status_code == 200
            print(f"{'✓' if success else '✗'} POST {url} → {r.status_code} ({elapsed:.1f}s)")

            if attempt < retries and (r.status_code >= 500 or r.status_code == 429):
                wait = 10 * 2**attempt if r.status_code == 429 else 2**attempt  # rate limits need longer backoff
                print(f"Retrying {r.status_code} in {wait}s (attempt {attempt + 1}/{retries + 1})...")
                time.sleep(wait)
                continue

            if r.status_code >= 400:
                error_body = r.text
                print(f"API Error {r.status_code}: {error_body}")
                r.reason = f"{r.reason}\n{error_body}"

            r.raise_for_status()
            return r.json(), elapsed
        except (requests.exceptions.ConnectionError, json.JSONDecodeError):
            # ConnectTimeout subclasses ConnectionError so it stays retryable; a ReadTimeout propagates instead,
            # because the request may have completed server-side and re-POSTing it would double-bill.
            if attempt < retries:
                print(f"Retrying API request in {2**attempt}s (attempt {attempt + 1}/{retries + 1})...")
                time.sleep(2**attempt)
                continue
            raise

    raise RuntimeError("OpenAI response failed without returning an HTTP response")


def _finalize_response_content(response_json: dict, text_format: dict | None) -> str | dict:
    """Extract assistant text, strip code fences, and decode structured JSON output when requested."""
    content = remove_outer_codeblocks(_openai_response_text(response_json))
    if text_format and text_format.get("format", {}).get("type") in ["json_object", "json_schema"]:
        return json.loads(content)
    return content


def _parse_tool_arguments(call: dict) -> dict:
    """Parse a Responses API function call argument payload."""
    arguments = call.get("arguments") or "{}"
    parsed = json.loads(arguments)
    if not isinstance(parsed, dict):
        raise TypeError("function call arguments must decode to an object")
    return parsed


def _handle_function_call(call: dict, tool_handlers: dict[str, Callable]) -> dict:
    """Execute one model-requested function call and return a Responses API output item."""
    name = call.get("name")
    call_id = call.get("call_id")
    try:
        if name not in tool_handlers:
            raise KeyError(f"Unknown tool: {name}")
        output = tool_handlers[name](**_parse_tool_arguments(call))
        if not isinstance(output, str):
            output = json.dumps(output)
    except Exception as e:
        output = f"{name or 'tool'} failed: {type(e).__name__}: {e}"
    return {"type": "function_call_output", "call_id": call_id, "output": output}


def get_agent_response(
    messages: list[dict[str, str]],
    tools: list[dict],
    tool_handlers: dict[str, Callable],
    text_format: dict | None = None,
    model: str | None = None,
    temperature: float = 1.0,
    reasoning_effort: str | None = None,
    max_turns: int = 6,
    max_cost: float = 0.0,
    parallel_tools: bool = False,
    retries: int = 2,
    request_timeout: tuple[int, int] = (30, 120),
) -> str | dict:
    """Run an iterative OpenAI Responses API agent with application-managed function tools.

    max_cost is a USD ceiling across all turns (0 disables); a tool request after reaching it aborts the incomplete
    agent run. Models missing from MODEL_COSTS disable max_cost loudly; max_turns still bounds. parallel_tools runs a
    turn's batched tool calls concurrently: opt in ONLY when every handler is thread-safe.
    """
    model = model or _get_default_model()
    if max_cost and model not in MODEL_COSTS:
        print(f"WARNING ⚠️ {model} missing from MODEL_COSTS; max_cost budget disabled (max_turns still applies)")
        max_cost = 0.0
    if _is_anthropic_model(model):
        print("Anthropic review model selected; falling back to single-shot response without local agent tools")
        return get_response(
            messages,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            text_format=text_format,
            model=model,
            tools=[t for t in tools if t.get("type") != "function"],
            retries=retries,
        )

    assert OPENAI_API_KEY, "OpenAI API key is required."
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    conversation = [m.copy() for m in messages]
    if conversation and conversation[0].get("role") == "system":
        conversation[0]["content"] += "\n\n" + SYSTEM_PROMPT_ADDITION

    base_data = {
        "model": model,
        "service_tier": "default",
        "store": True,
        "temperature": temperature,
        "tools": tools,
        "tool_choice": "auto",
        "parallel_tool_calls": True,  # batched tool calls share one turn, so the history is re-billed fewer times
    }
    if "gpt-5" in model:
        base_data["reasoning"] = {"effort": reasoning_effort or "low"}
    if text_format:
        base_data["text"] = text_format

    tool_calls = []
    total_elapsed = 0.0
    total_cost = 0.0
    total_usage = None
    previous_response_id = None
    next_input = conversation
    turn = -1
    for turn in range(max_turns):
        data = {**base_data, "input": next_input}
        if previous_response_id:
            data["previous_response_id"] = previous_response_id
        response_json, elapsed = _post_openai_response(data, headers, retries, request_timeout)
        total_elapsed += elapsed
        total_usage = _add_openai_usage(total_usage, response_json)
        previous_response_id = response_json.get("id")
        output_items = response_json.get("output", [])
        turn_calls = _response_tool_calls(output_items)
        turn_cost = (
            _openai_usage_cost(response_json.get("usage") or {}, model)
            + turn_calls.count("web_search") * WEB_SEARCH_CALL_COST
        )
        total_cost += turn_cost
        tool_calls += turn_calls
        _print_openai_usage(
            response_json,
            model,
            elapsed,
            f"turn {turn + 1}/{max_turns}, {_format_tool_calls(turn_calls)}",
            turn_cost,
        )
        function_calls = [item for item in output_items if item.get("type") == "function_call"]

        if not function_calls:
            _print_openai_usage(
                {"usage": total_usage},
                model,
                total_elapsed,
                f"agent total, {turn + 1} turns, {_format_tool_calls(tool_calls)}",
                total_cost,
            )
            return _finalize_response_content(response_json, text_format)

        if not previous_response_id:
            raise RuntimeError("OpenAI response did not include an id for server-managed continuation")
        if max_cost and total_cost >= max_cost:
            raise RuntimeError(f"Agent cost budget ${max_cost:.2f} reached before requested tools could run")
        if parallel_tools and len(function_calls) > 1:  # opt-in contract: handlers must be thread-safe
            with ThreadPoolExecutor(max_workers=min(8, len(function_calls))) as pool:
                next_input = list(pool.map(lambda call: _handle_function_call(call, tool_handlers), function_calls))
        else:
            next_input = [_handle_function_call(call, tool_handlers) for call in function_calls]

    final_instruction = {
        "role": "user",
        "content": (
            "You have used all available tool-calling steps. Do not call tools. Synthesize the gathered tool results "
            "and return the best final answer now in the required response format. If the gathered context is "
            "incomplete, say so in the final answer instead of dumping raw tool output."
        ),
    }
    data = {**base_data, "input": [*next_input, final_instruction], "tool_choice": "none"}
    if previous_response_id:
        data["previous_response_id"] = previous_response_id
    response_json, elapsed = _post_openai_response(data, headers, max(retries, 2), request_timeout)
    total_elapsed += elapsed
    total_usage = _add_openai_usage(total_usage, response_json)
    total_cost += _openai_usage_cost(response_json.get("usage") or {}, model)
    _print_openai_usage(response_json, model, elapsed, f"turn final/{max_turns}, 0 tools")
    _print_openai_usage(
        {"usage": total_usage},
        model,
        total_elapsed,
        f"agent total, {turn + 2} turns, {_format_tool_calls(tool_calls)}",
        total_cost,
    )
    return _finalize_response_content(response_json, text_format)


def get_response(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),
    temperature: float = 1.0,
    reasoning_effort: str | None = None,
    text_format: dict | None = None,
    model: str | None = None,
    tools: list[dict] | None = None,
    retries: int = 2,
    background: bool = False,
) -> str | dict:
    """Generates a completion using OpenAI or Anthropic API with retry logic."""
    model = model or _get_default_model()
    is_anthropic = _is_anthropic_model(model)
    background = background and not is_anthropic

    # Validate API key
    if is_anthropic:
        assert ANTHROPIC_API_KEY, "Anthropic API key is required for Claude models."
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    else:
        assert OPENAI_API_KEY, "OpenAI API key is required."
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    # Extract system message and append guidance
    system_content = ""
    user_messages = messages.copy()
    if user_messages and user_messages[0].get("role") == "system":
        system_content = user_messages.pop(0)["content"] + "\n\n" + SYSTEM_PROMPT_ADDITION
        if not is_anthropic:
            # For OpenAI, keep system message in messages list with addition
            messages = [{"role": "system", "content": system_content}, *user_messages]

    for attempt in range(retries + 1):
        if is_anthropic:
            data = {
                "model": model,
                "max_tokens": 32000,  # large replies (reviews) exceed 8192; truncated schema output is unusable
                "messages": user_messages,
            }
            if temperature != 1.0:  # 1.0 is the API default; newer Claude models 400 on explicit non-default values
                data["temperature"] = temperature
            if system_content:
                data["system"] = system_content
            # Tools (web_search) are not forwarded to Anthropic (caused empty responses with JSON schema)
            # Handle structured JSON output for Anthropic
            if text_format and text_format.get("format", {}).get("type") == "json_schema":
                schema = text_format["format"].get("schema", {})
                # Add JSON instruction to system prompt
                json_instruction = f"\n\nRespond ONLY with valid JSON matching this schema:\n{json.dumps(schema)}"
                data["system"] = (data.get("system") or "") + json_instruction
        else:
            data = {"model": model, "input": messages, "store": background, "temperature": temperature}
            if background:
                data["background"] = True
            if "gpt-5" in model:
                data["reasoning"] = {"effort": reasoning_effort or "low"}
            if text_format:
                data["text"] = text_format
            if tools:
                data["tools"] = tools

        try:
            started = time.time()
            r = requests.post(url, json=data, headers=headers, timeout=(30, 900))
            elapsed = r.elapsed.total_seconds()
            success = r.status_code == 200
            print(f"{'✓' if success else '✗'} POST {url} → {r.status_code} ({elapsed:.1f}s)")

            # Retry server errors and rate limits (a 429 rejection executed nothing, so retrying is side-effect free)
            if attempt < retries and (r.status_code >= 500 or r.status_code == 429):
                wait = 10 * 2**attempt if r.status_code == 429 else 2**attempt  # rate limits need longer backoff
                print(f"Retrying {r.status_code} in {wait}s (attempt {attempt + 1}/{retries + 1})...")
                time.sleep(wait)
                continue

            if r.status_code >= 400:
                error_body = r.text
                print(f"API Error {r.status_code}: {error_body}")
                r.reason = f"{r.reason}\n{error_body}"

            r.raise_for_status()

            # Parse response
            response_json = r.json()
            if background:
                response_json = _poll_openai_response(response_json, headers)
                elapsed = time.time() - started
            if is_anthropic:
                content = ""
                for block in response_json.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text") or ""
                content = content.strip()

                _print_openai_usage(response_json, model, elapsed)
                if response_json.get("stop_reason") == "max_tokens" and text_format:
                    # A truncated schema-constrained reply is partial JSON; fail clearly instead of at json.loads
                    raise RuntimeError(f"{model} response truncated at max_tokens; structured output is incomplete")
            else:
                content = _openai_response_text(response_json)
                _print_openai_usage(response_json, model, elapsed)

            if text_format and text_format.get("format", {}).get("type") in ["json_object", "json_schema"]:
                content = remove_outer_codeblocks(content)
                return json.loads(content)

            content = remove_outer_codeblocks(content)
            for x in remove:
                content = content.replace(x, "")

            # Retry on bad links, feeding the broken URLs back so the model fixes them instead of rolling the dice
            if check_links and (bad_urls := check_links_in_string(content, return_bad=True)[1]):
                if attempt < retries:
                    print(f"Bad URLs detected, retrying with feedback: {bad_urls}")
                    feedback = [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": "Broken links in your reply: " + ", ".join(bad_urls) + ". "
                            "Rewrite the full reply, replacing each broken link with a working one or removing it.",
                        },
                    ]
                    messages = [*messages, *feedback]
                    user_messages = [*user_messages, *feedback]
                    continue
                content = check_links_in_string(content, replace=True)  # final attempt: salvage via redirects/search

            return content

        except (requests.exceptions.ConnectionError, json.JSONDecodeError) as e:
            # ConnectTimeout subclasses ConnectionError so it stays retryable; a ReadTimeout propagates instead,
            # because the request may have completed server-side and re-POSTing it would double-bill.
            if attempt < retries:
                print(f"Retrying {e.__class__.__name__} in {2**attempt}s (attempt {attempt + 1}/{retries + 1})...")
                time.sleep(2**attempt)
                continue
            raise


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
        {"role": "user", "content": "Explain how to export a YOLO26 model to CoreML."},
    ]
    response = get_response(messages)
    print(response)
