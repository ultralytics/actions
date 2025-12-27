# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

from .anthropic_utils import ANTHROPIC_API_KEY
from .anthropic_utils import get_response as _anthropic_get_response
from .common_utils import (
    ACTIONS_CREDIT,
    REDIRECT_END_IGNORE_LIST,
    REDIRECT_START_IGNORE_LIST,
    REQUESTS_HEADERS,
    SKIP_PATTERNS,
    URL_IGNORE_LIST,
    allow_redirect,
    filter_diff_text,
    format_skipped_files_dropdown,
    format_skipped_files_note,
    remove_html_comments,
    should_skip_file,
)
from .github_utils import GITHUB_API_URL, GITHUB_GRAPHQL_URL, Action, ultralytics_actions_info
from .openai_utils import (
    MAX_PROMPT_CHARS,
    filter_labels,
    get_pr_open_response,
    get_pr_summary_guidelines,
    get_pr_summary_prompt,
    sanitize_ai_text,
)
from .openai_utils import get_response as _openai_get_response
from .version_utils import check_pubdev_version, check_pypi_version


def get_response(
    messages: list[dict[str, str]],
    check_links: bool = True,
    remove: list[str] = (" @giscus[bot]",),
    temperature: float = 1.0,
    reasoning_effort: str | None = None,
    text_format: dict | None = None,
    model: str | None = None,
    tools: list[dict] | None = None,
) -> str | dict:
    """Route to appropriate LLM provider based on available API keys (Anthropic takes priority)."""
    kwargs = {
        "messages": messages,
        "check_links": check_links,
        "remove": remove,
        "temperature": temperature,
        "reasoning_effort": reasoning_effort,
        "text_format": text_format,
        "tools": tools,
    }
    if model is not None:
        kwargs["model"] = model
    return _anthropic_get_response(**kwargs) if ANTHROPIC_API_KEY else _openai_get_response(**kwargs)


__all__ = (
    "ACTIONS_CREDIT",
    "GITHUB_API_URL",
    "GITHUB_GRAPHQL_URL",
    "MAX_PROMPT_CHARS",
    "REDIRECT_END_IGNORE_LIST",
    "REDIRECT_START_IGNORE_LIST",
    "REQUESTS_HEADERS",
    "SKIP_PATTERNS",
    "URL_IGNORE_LIST",
    "Action",
    "allow_redirect",
    "check_pubdev_version",
    "check_pypi_version",
    "filter_diff_text",
    "filter_labels",
    "format_skipped_files_dropdown",
    "format_skipped_files_note",
    "get_pr_open_response",
    "get_pr_summary_guidelines",
    "get_pr_summary_prompt",
    "get_response",
    "remove_html_comments",
    "sanitize_ai_text",
    "should_skip_file",
    "ultralytics_actions_info",
)
