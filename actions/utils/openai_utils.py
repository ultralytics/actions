# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import requests

from actions.utils.common_utils import check_links_in_string, format_skipped_files_note

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("MODEL")  # Auto-detected from API keys if not set
REVIEW_MODEL = os.getenv("REVIEW_MODEL")  # Optional override for PR reviews
MAX_PROMPT_CHARS = round(128000 * 3.3 * 0.5)  # deliberate COST ceiling, not a context limit; agent tools read the rest
WEB_SEARCH_CALL_COST = 0.01  # $10 per 1K calls

# Default models (single source of truth)
OPENAI_MODEL_DEFAULT = "gpt-6-luna"
ANTHROPIC_MODEL_DEFAULT = "claude-haiku-5-5"
OPENAI_REVIEW_MODEL_DEFAULT = "gpt-6-luna"
ANTHROPIC_REVIEW_MODEL_DEFAULT = "claude-haiku-5-5"

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
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-5-nano-2025-08-07": (0.05, 0.40),
    "gpt-5-mini-2025-08-07": (0.25, 2.00),
    # Anthropic Claude models
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),  # 5x above 100K prompt tokens, see _openai_usage_cost
    "claude-opus-4-5-20251101": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-fable-5-1": (10.00, 50.00),
}
SYSTEM_PROMPT_ADDITION = """Guidance:
  - Ultralytics Branding: Use YOLO11, YOLO26, etc., not YOLOv11, YOLOv26 (only older versions like YOLOv10 have a v).
  - YOLO26: Latest stable and recommended Ultralytics model for all use cases. See https://docs.ultralytics.com/models/yolo26 for details.
  - Ultralytics Platform: The simplest way to annotate datasets, train and deploy YOLO models at https://platform.ultralytics.com.
  - Avoid Equations: Do not include equations or mathematical notations.
  - Markdown: Reply in Markdown format.
  - Links: Use descriptive anchor text for all URLs.
  - Code:
    - Provide minimal code examples only when supported by the repository context.
    - Use inline backticks or a fenced block with the repository's appropriate language.
    - Verify argument names, methods, classes, files, package managers, and commands before including them.
  - Use the "@" symbol to refer to GitHub users, e.g. @glenn-jocher.
  - Tone: Adopt a professional, friendly, and concise tone.
"""
_CITATION_PATTERN = re.compile(
    r"[\uE000-\uF8FF]*(?:\bcite[\uE000-\uF8FF]*(turn\d+(?:search|view)\d+|[\w\d]+)[\uE000-\uF8FF]*|\bturn\d+(?:search|view)\d+[\uE000-\uF8FF]+)"
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
    current_labels = {label.lower() for label in (current_labels or [])}
    excluded = {
        "help wanted",
        "todo",
        "research",
        "non-reproducible",
        "popular",
        "invalid",
        "stale",
        "wontfix",
        "duplicate",
    }
    filtered = {
        name: description
        for name, description in available_labels.items()
        if name.lower() not in excluded | current_labels
    }

    if "bug" in current_labels:
        filtered = {name: description for name, description in filtered.items() if name.lower() != "question"}
    elif "question" in current_labels:
        filtered = {name: description for name, description in filtered.items() if name.lower() != "bug"}

    if "alert" not in current_labels and not any(name.lower() == "alert" for name in filtered):
        filtered["Alert"] = (
            "Potential spam, abuse, or illegal activity including advertising, unsolicited promotions, malware, "
            "phishing, crypto offers, pirated software or media, free movie downloads, cracks, keygens or any other "
            "content that violates terms of service or legal standards."
        )

    return filtered


def get_pr_summary_guidelines() -> str:
    """Returns PR summary formatting guidelines (used by both unified PR open and PR update/merge)."""
    return """Summarize the implemented change, not the author's intentions. Ground every statement in the diff and PR context; never invent behavior, test results, compatibility claims, or user impact. Name the concrete components and behaviors changed, consolidate related edits, and omit file-by-file narration and generic praise. Use concise plain language for maintainers and users. Your response must include exactly these 3 sections with H3 Markdown headers (do not use H1 or H2 headers):

### 🌟 Summary
(one sentence stating what changed and why)

### 📊 Key Changes
- (2-5 specific bullets, ordered by importance)

### 🎯 Purpose & Impact
- (specific behavior or workflow impact; say "No user-facing change" when appropriate)"""


def get_pr_summary_prompt(
    repository: str, diff: tuple[str, list[str]], title: str = "", description: str = ""
) -> tuple[str, bool]:
    """Return the complete PR summary generation prompt."""
    diff_text, skipped_files = diff
    prompt = (
        f"{get_pr_summary_guidelines()}\n\nRepository: {repository}\nPR title: {title}\n"
        f"PR description:\n{description[:8000]}\n\nPR diff:\n{diff_text[:MAX_PROMPT_CHARS]}"
    )
    prompt += format_skipped_files_note(skipped_files)
    return prompt, len(diff_text) > MAX_PROMPT_CHARS


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
    """Get model for PR reviews: REVIEW_MODEL if set, else the review default of the auto-detected provider."""
    if REVIEW_MODEL:
        return REVIEW_MODEL
    return ANTHROPIC_REVIEW_MODEL_DEFAULT if _is_anthropic_model(_get_default_model()) else OPENAI_REVIEW_MODEL_DEFAULT


def _anthropic_request(
    messages: list[dict], model: str, reasoning_effort: str | None = None, text_format: dict | None = None
) -> tuple[dict, dict]:
    """Build Messages API headers and payload from OpenAI-style messages, mirroring Responses API reasoning and JSON."""
    assert ANTHROPIC_API_KEY, "Anthropic API key is required for Claude models."
    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    data = {
        "model": model,
        "max_tokens": 32000,  # large replies (reviews) exceed 8192; truncated schema output is unusable
        "messages": [m for m in messages if m["role"] != "system"],
    }
    if system := "\n\n".join(m["content"] for m in messages if m["role"] == "system"):
        data["system"] = system
    if not model.startswith(("claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-5")):  # adaptive needs 4.6+
        data["thinking"] = {"type": "adaptive"}  # explicit: Opus 4.6-4.8 and Sonnet 4.6 do not think by default
        data["output_config"] = {"effort": reasoning_effort or "medium"}
    if text_format and text_format.get("format", {}).get("type") == "json_schema":
        data.setdefault("output_config", {})["format"] = {
            "type": "json_schema",
            "schema": text_format["format"]["schema"],
        }
    return headers, data


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


def _response_text(response_json: dict) -> str:
    """Extract assistant text from an OpenAI Responses or Anthropic Messages API response."""
    blocks = response_json.get("content") or [
        c for item in response_json.get("output", []) if item.get("type") == "message" for c in item.get("content", [])
    ]
    return "".join(b.get("text") or "" for b in blocks if b.get("type") in {"output_text", "text"}).strip()


def _response_tool_calls(output_items: list[dict]) -> list[str]:
    """Name Responses API tool-call items (web_search_call -> web_search) and Messages API tool_use blocks."""
    return [
        item.get("name") or (item.get("type") or "")[: -len("_call")]  # removesuffix needs py3.9+, repo floor is 3.8
        for item in output_items
        if (item.get("type") or "").endswith("_call") or item.get("type") in {"tool_use", "server_tool_use"}
    ]


def _thinking_tokens(usage: dict) -> int:
    """Return reasoning tokens from OpenAI Responses or thinking tokens from Anthropic Messages usage."""
    details = usage.get("output_tokens_details") or {}
    return details.get("reasoning_tokens", 0) or details.get("thinking_tokens", 0)


def _add_openai_usage(total_usage: dict | None, response_json: dict) -> dict | None:
    """Add one Responses or Messages API usage block into a cumulative Responses-shaped usage block."""
    usage = response_json.get("usage")
    if not usage:
        return total_usage

    total_usage = total_usage or {
        "input_tokens": 0,
        "output_tokens": 0,
        "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }
    input_tokens, cached_tokens, cache_write_tokens = _normalize_usage_tokens(usage)
    total_usage["input_tokens"] += input_tokens
    total_usage["output_tokens"] += usage.get("output_tokens", 0)
    total_usage["input_tokens_details"]["cached_tokens"] += cached_tokens
    total_usage["input_tokens_details"]["cache_write_tokens"] += cache_write_tokens
    total_usage["output_tokens_details"]["reasoning_tokens"] += _thinking_tokens(usage)
    return total_usage


def _normalize_usage_tokens(usage: dict) -> tuple[int, int, int]:
    """Return input, cache-read, and cache-write tokens for OpenAI Responses or Anthropic Messages usage shapes.

    Anthropic reports cache reads/writes outside input_tokens, so both fold back into the input total and reads count as
    cached — the same normalization ultralytics/assistant applies, keeping cross-repo telemetry identical.
    """
    cache_read, cache_write = usage.get("cache_read_input_tokens", 0), usage.get("cache_creation_input_tokens", 0)
    input_tokens = usage.get("input_tokens", 0) + cache_read + cache_write
    details = usage.get("input_tokens_details") or {}
    cached_tokens = details.get("cached_tokens", 0) or cache_read
    cache_write_tokens = details.get("cache_write_tokens", 0) or cache_write
    return input_tokens, cached_tokens, cache_write_tokens


def _openai_usage_cost(usage: dict, model: str) -> float:
    """Compute billed USD cost including cache reads/writes and GPT-5.6/GPT-6/Haiku 5.5 long-prompt rates."""
    costs = MODEL_COSTS.get(model, (0.0, 0.0))
    input_tokens, cached_tokens, cache_write_tokens = _normalize_usage_tokens(usage)
    cache_read_rate = {"claude-fable-5-1": 0.025, "claude-opus-5-5": 0.05, "claude-sonnet-5-5": 0.05}.get(model, 0.1)
    cache_write_premium = cache_write_tokens * 0.25 if model.startswith(("gpt-5.6-", "gpt-6-", "claude")) else 0
    billed_input = input_tokens - cached_tokens * (1 - cache_read_rate) + cache_write_premium
    if model.startswith(("gpt-5.6-", "gpt-6-")) and input_tokens > 272000:
        input_rate, output_rate = 2, 1.5
    elif model == "claude-haiku-5-5" and input_tokens > 100000:  # $0.50/$2.50 above 100K prompt tokens
        input_rate, output_rate = 5, 5
    else:
        input_rate = output_rate = 1
    return (billed_input * costs[0] * input_rate + usage.get("output_tokens", 0) * costs[1] * output_rate) / 1e6


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
    """Print token/cost telemetry: 'model: 136036→289 tokens (72% cached, 8% cache write), $0.69, 8.9s'."""
    if usage := response_json.get("usage"):
        input_tokens, cached_tokens, cache_write_tokens = _normalize_usage_tokens(usage)
        output_tokens = usage.get("output_tokens", 0)  # includes thinking, noted in the parenthetical
        thinking_tokens = _thinking_tokens(usage)
        cost = _openai_usage_cost(usage, model) if billed_cost is None else billed_cost
        notes = []
        if cached_tokens:
            notes.append(f"{round(100 * cached_tokens / input_tokens)}% cached")
        if cache_write_tokens:
            notes.append(f"{round(100 * cache_write_tokens / input_tokens)}% cache write")
        if thinking_tokens:
            notes.append(f"{thinking_tokens} thinking")
        note_str = f" ({', '.join(notes)})" if notes else ""
        metadata = f", {metadata}" if metadata else ""
        cost_str = f"${cost:.2f}" if cost == 0 or cost >= 0.01 else f"${cost:.5f}"  # match ultralytics/assistant
        print(f"{model}: {input_tokens}→{output_tokens} tokens{note_str}, {cost_str}, {elapsed:.1f}s{metadata}")


def _post_response(
    url: str, data: dict, headers: dict, retries: int, request_timeout: tuple[int, int]
) -> tuple[dict, float]:
    """Post to the Responses or Messages API with the same transient retry policy as get_response()."""
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
            response_json = r.json()
            return (
                _poll_openai_response(response_json, headers) if response_json.get("status") else response_json
            ), elapsed
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, json.JSONDecodeError):
            # Retry TLS/read timeouts too, accepting that a response timeout may repeat an already-billed request.
            if attempt < retries:
                print(f"Retrying API request in {2**attempt}s (attempt {attempt + 1}/{retries + 1})...")
                time.sleep(2**attempt)
                continue
            raise

    raise RuntimeError(f"POST {url} failed without returning an HTTP response")


def _finalize_response_content(response_json: dict, text_format: dict | None) -> str | dict:
    """Extract assistant text, strip code fences, and decode structured JSON output when requested."""
    content = remove_outer_codeblocks(_response_text(response_json))
    if text_format and text_format.get("format", {}).get("type") in ["json_object", "json_schema"]:
        return json.loads(content)
    return content


def _parse_tool_arguments(call: dict) -> dict:
    """Parse a Responses API function call argument payload or a Messages API tool_use input."""
    parsed = call["input"] if "input" in call else json.loads(call.get("arguments") or "{}")
    if not isinstance(parsed, dict):
        raise TypeError("function call arguments must decode to an object")
    return parsed


def _handle_function_call(call: dict, tool_handlers: dict[str, Callable]) -> dict:
    """Execute one model-requested function call and return a Responses API output item or Messages API tool_result."""
    name = call.get("name")
    try:
        if name not in tool_handlers:
            raise KeyError(f"Unknown tool: {name}")
        output = tool_handlers[name](**_parse_tool_arguments(call))
        if not isinstance(output, str):
            output = json.dumps(output)
    except Exception as e:
        # The model owns a failed call: it can correct the arguments, use another tool, or report the evidence gap
        print(f"Tool {name} failed: {e!r}")
        output = f"Tool {name} failed: {type(e).__name__}: {e}"
    if call.get("type") == "tool_use":
        return {"type": "tool_result", "tool_use_id": call.get("id"), "content": output}
    return {"type": "function_call_output", "call_id": call.get("call_id"), "output": output}


def get_agent_response(
    messages: list[dict[str, str]],
    tools: list[dict],
    tool_handlers: dict[str, Callable],
    text_format: dict | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_turns: int = 6,
    max_cost: float = 0.0,
    parallel_tools: bool = False,
    retries: int = 2,
    request_timeout: tuple[int, int] = (30, 300),  # responses are unstreamed, so the read timeout caps generation
) -> str | dict:
    """Run an iterative OpenAI Responses or Anthropic Messages API agent with application-managed function tools.

    Tools are Responses API definitions; Claude models receive the Messages API equivalents, with hosted web_search
    mapped to Anthropic's server-side web search. max_cost is a USD ceiling across all turns (0 disables); a tool
    request after reaching it aborts the incomplete agent run. Models missing from MODEL_COSTS disable max_cost loudly;
    max_turns still bounds. parallel_tools runs a turn's batched tool calls concurrently: opt in ONLY when every handler
    is thread-safe.
    """
    model = model or _get_default_model()
    if max_cost and model not in MODEL_COSTS:
        print(f"WARNING ⚠️ {model} missing from MODEL_COSTS; max_cost budget disabled (max_turns still applies)")
        max_cost = 0.0
    conversation = [m.copy() for m in messages]
    if conversation and conversation[0].get("role") == "system":
        conversation[0]["content"] += "\n\n" + SYSTEM_PROMPT_ADDITION

    is_anthropic = _is_anthropic_model(model)
    if is_anthropic:
        url = "https://api.anthropic.com/v1/messages"
        headers, base_data = _anthropic_request(conversation, model, reasoning_effort, text_format)
        history, next_input = [], base_data.pop("messages")  # stateless API: every turn resends the full history
        base_data["tools"] = [
            {"type": "web_search_20250305", "name": "web_search"}
            if t["type"] == "web_search"
            else {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
                "strict": t.get("strict", False),
            }
            for t in tools
        ]
        base_data["cache_control"] = {"type": "ephemeral"}  # automatic caching re-reads the history each turn
    else:
        assert OPENAI_API_KEY, "OpenAI API key is required."
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        next_input = conversation
        base_data = {
            "model": model,
            "service_tier": "default",
            "store": True,
            "tools": tools,
            "parallel_tool_calls": True,  # batched tool calls share one turn, so the history is re-billed fewer times
            "prompt_cache_key": f"agent-run:{uuid4().hex}",
            # Overflow guard only: compaction collapses the run to a few thousand tokens and drops the evidence gathered
            # so far, so it only fires at the long-context billing boundary (2x input above 272k tokens on gpt-5.6/6)
            "context_management": [{"type": "compaction", "compact_threshold": 272_000}],
        }
        if any(x in model for x in ("gpt-5", "gpt-6")):
            base_data["reasoning"] = {"effort": reasoning_effort or "medium"}
        if text_format:
            base_data["text"] = text_format

    tool_calls = []
    total_elapsed = 0.0
    total_cost = 0.0
    total_usage = None
    previous_response_id = None
    tool_choice = "auto" if max_turns > 0 else "none"
    repaired = False
    # Up to two tool-free turns follow the tool turns: a forced synthesis once max_turns is spent, then one repair
    # of a malformed structured reply. A Claude pause_turn also spends a turn, so the range can run out.
    for turn in range(max_turns + 2):
        if is_anthropic:
            history += next_input
            data = {**base_data, "messages": history, "tool_choice": {"type": tool_choice}}
        else:
            data = {**base_data, "input": next_input, "tool_choice": tool_choice}
            if previous_response_id:
                data["previous_response_id"] = previous_response_id
        response_json, elapsed = _post_response(
            url, data, headers, retries if tool_choice == "auto" else max(retries, 2), request_timeout
        )
        total_elapsed += elapsed
        total_usage = _add_openai_usage(total_usage, response_json)
        previous_response_id = response_json.get("id")
        output_items = response_json.get("content" if is_anthropic else "output", [])
        if is_anthropic:
            history.append({"role": "assistant", "content": output_items})  # echoed verbatim, thinking blocks included
        if any(item.get("type") == "compaction" for item in output_items):
            print("WARNING ⚠️ context compacted server-side; earlier tool results are summarized, not verbatim")
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
            f"turn {turn + 1 if tool_choice == 'auto' else 'final'}/{max_turns}, {_format_tool_calls(turn_calls)}",
            turn_cost,
        )
        function_calls = [item for item in output_items if item.get("type") in {"function_call", "tool_use"}]

        if function_calls:
            if not previous_response_id:
                raise RuntimeError("OpenAI response did not include an id for server-managed continuation")
            if max_cost and total_cost >= max_cost:
                raise RuntimeError(f"Agent cost budget ${max_cost:.2f} reached before requested tools could run")
            if parallel_tools and len(function_calls) > 1:  # opt-in contract: handlers must be thread-safe
                with ThreadPoolExecutor(max_workers=min(8, len(function_calls))) as pool:
                    outputs = list(pool.map(lambda call: _handle_function_call(call, tool_handlers), function_calls))
            else:
                outputs = [_handle_function_call(call, tool_handlers) for call in function_calls]
            next_input = [{"role": "user", "content": outputs}] if is_anthropic else outputs
            if turn + 1 >= max_turns:  # tool turns are spent: the next turn must synthesize from what was gathered
                instruction = (
                    "You have used all available tool-calling steps. Do not call tools. Synthesize the gathered tool "
                    "results and return the best final answer now in the required response format. If the gathered "
                    "context is incomplete, say so in the final answer instead of dumping raw tool output."
                )
                if not is_anthropic:
                    next_input.append({"role": "user", "content": instruction})
                # Text after tool results ends Claude's turn, which a web search deferred behind this batch rejects
                elif {b.get("id") for b in output_items if b.get("type") == "server_tool_use"} <= {
                    b.get("tool_use_id") for b in output_items
                }:
                    outputs.append({"type": "text", "text": instruction})
                tool_choice = "none"
            continue
        if response_json.get("stop_reason") == "pause_turn":  # Claude paused a long web search: resend to resume
            next_input = []
            continue

        try:
            content = _finalize_response_content(response_json, text_format)
        except json.JSONDecodeError as e:
            # A completed reply can still carry malformed or cut-off JSON; ask once for the full object before failing
            text = _response_text(response_json)
            print(f"Malformed structured output ({e}) in {len(text)} chars ending {text[-200:]!r}")
            if repaired or not previous_response_id:
                raise
            repaired = True
            next_input = [
                {
                    "role": "user",
                    "content": (
                        f"Your previous reply was not valid JSON for the required response format ({e}). "
                        "Return the complete JSON object now, and nothing else."
                    ),
                }
            ]
            tool_choice = "none"
            continue
        _print_openai_usage(
            {"usage": total_usage},
            model,
            total_elapsed,
            f"agent total, {turn + 1} turns, {_format_tool_calls(tool_calls)}",
            total_cost,
        )
        return content
    raise RuntimeError(f"Agent made no final reply within {max_turns + 2} turns")


def get_response(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),
    reasoning_effort: str | None = None,
    text_format: dict | None = None,
    model: str | None = None,
    retries: int = 2,
    background: bool = False,
) -> str | dict:
    """Generates a completion using OpenAI or Anthropic API with retry logic."""
    model = model or _get_default_model()
    is_anthropic = _is_anthropic_model(model)
    background = background and not is_anthropic

    if messages and messages[0].get("role") == "system":  # append guidance without mutating the caller's messages
        messages = [
            {"role": "system", "content": messages[0]["content"] + "\n\n" + SYSTEM_PROMPT_ADDITION},
            *messages[1:],
        ]
    if is_anthropic:
        url = "https://api.anthropic.com/v1/messages"
    else:
        assert OPENAI_API_KEY, "OpenAI API key is required."
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    for attempt in range(retries + 1):
        if is_anthropic:
            headers, data = _anthropic_request(messages, model, reasoning_effort, text_format)
        else:
            data = {"model": model, "input": messages, "store": background}
            if model.startswith(("gpt-5.6-luna", "gpt-6-luna")):
                data["prompt_cache_options"] = {"mode": "explicit"}  # disable costly implicit writes for one-shot calls
            if background:
                data["background"] = True
            if any(x in model for x in ("gpt-5", "gpt-6")):
                data["reasoning"] = {"effort": reasoning_effort or "medium"}
            if text_format:
                data["text"] = text_format

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
            if background or response_json.get("status"):  # only OpenAI Responses carry a status
                response_json = _poll_openai_response(response_json, headers)
                elapsed = time.time() - started
            _print_openai_usage(response_json, model, elapsed)
            if (stop_reason := response_json.get("stop_reason")) in {"max_tokens", "refusal"} and text_format:
                # A truncated or refused schema-constrained Claude reply is not the schema; fail clearly, not at json.loads
                raise RuntimeError(f"{model} stopped with {stop_reason}; structured output is incomplete")
            content = _response_text(response_json)

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
                    continue
                content = check_links_in_string(content, replace=True)  # final attempt: salvage via redirects/search

            return content

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, json.JSONDecodeError) as e:
            # Retry TLS/read timeouts too, accepting that a response timeout may repeat an already-billed request.
            if attempt < retries:
                print(f"Retrying {e.__class__.__name__} in {2**attempt}s (attempt {attempt + 1}/{retries + 1})...")
                time.sleep(2**attempt)
                continue
            raise


def get_pr_open_response(
    repository: str,
    diff: tuple[str, list[str]],
    title: str,
    username: str,
    available_labels: dict,
    description: str = "",
    repository_context: str = "",
    summarize: bool = True,
    current_labels: list | None = None,
) -> dict:
    """Generate a PR summary and labels in a single API call."""
    diff_text, skipped_files = diff
    is_large = len(diff_text) > MAX_PROMPT_CHARS

    filtered_labels = filter_labels(available_labels, current_labels) if available_labels else {}
    labels_str = "\n".join(f"- {name}: {description}" for name, description in filtered_labels.items())
    summary_instructions = get_pr_summary_guidelines() if summarize else "Return an empty summary string."
    label_instructions = (
        "Array of 1-3 most relevant label names. Only use Alert with high confidence for inappropriate PRs. "
        f"Return an empty array if no label is relevant. Available labels:\n{labels_str}"
        if filtered_labels
        else "Return an empty labels array."
    )
    prompt = f"""You are processing a new GitHub PR by @{username} for the {repository} repository.

Repository context: {repository_context or "No additional metadata provided."}
PR description: {description[:8000] or "No description provided."}

Generate 2 outputs in a single JSON response for the PR titled '{title}' with the following diff:
{diff_text[:MAX_PROMPT_CHARS]}{format_skipped_files_note(skipped_files)}


--- FIRST JSON OUTPUT (PR SUMMARY) ---
{summary_instructions}

--- SECOND JSON OUTPUT (PR LABELS) ---
{label_instructions}"""

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "PR summary with emoji sections"},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Array of label names"},
        },
        "required": ["summary", "labels"],
        "additionalProperties": False,
    }

    messages = [
        {"role": "system", "content": "You are an Ultralytics AI assistant processing GitHub PRs."},
        {"role": "user", "content": prompt},
    ]
    result = get_response(
        messages,
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
