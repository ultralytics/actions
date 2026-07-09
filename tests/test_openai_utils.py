# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

import requests

from actions.utils.openai_utils import (
    MODEL_COSTS,
    OPENAI_MODEL_DEFAULT,
    PR_REVIEW_MODEL_DEFAULT,
    _is_anthropic_model,
    _response_tool_calls,
    get_agent_response,
    get_response,
    get_review_model,
    remove_outer_codeblocks,
)


def test_default_models():
    """Test canonical default models are priced so max_cost budgets stay enforceable."""
    assert OPENAI_MODEL_DEFAULT == "gpt-5.6-sol"
    assert PR_REVIEW_MODEL_DEFAULT == "gpt-5.6-sol"
    assert OPENAI_MODEL_DEFAULT in MODEL_COSTS  # unpriced models disable max_cost budgets
    assert PR_REVIEW_MODEL_DEFAULT in MODEL_COSTS
    assert MODEL_COSTS["gpt-5.6-sol"] == (5.00, 30.00)
    assert MODEL_COSTS["gpt-5.6-terra"] == (2.50, 15.00)
    assert MODEL_COSTS["gpt-5.6-luna"] == (1.00, 6.00)


def test_is_anthropic_model():
    """Test model provider detection."""
    assert _is_anthropic_model("claude-sonnet-4-6") is True
    assert _is_anthropic_model("claude-haiku-4-5-20251001") is True
    assert _is_anthropic_model("claude-opus-4-7") is True
    assert _is_anthropic_model("gpt-5.6-sol") is False
    assert _is_anthropic_model("gpt-5-mini-2025-08-07") is False


def test_response_tool_calls():
    """Test Responses API tool-call item naming, including hosted tools without a name field."""
    output_items = [
        {"type": "function_call", "name": "lookup_value"},
        {"type": "web_search_call"},
        {"type": "message"},
        {"type": "function_call_output"},
    ]
    assert _response_tool_calls(output_items) == ["lookup_value", "web_search"]


def test_remove_outer_codeblocks():
    """Test removing outer code block markers from strings."""
    # Test with python code block
    input_str = "```python\ndef test():\n    return True\n```"
    expected = "def test():\n    return True"
    assert remove_outer_codeblocks(input_str) == expected

    # Test with no language specified
    input_str = "```\ndef test():\n    return True\n```"
    expected = "def test():\n    return True"
    assert remove_outer_codeblocks(input_str) == expected

    # Test with no code blocks
    input_str = "def test():\n    return True"
    assert remove_outer_codeblocks(input_str) == input_str


def test_get_review_model_override():
    """Test review model override logic."""
    with patch("actions.utils.openai_utils.REVIEW_MODEL", "claude-opus-4-7"):
        with patch("actions.utils.openai_utils.MODEL", "gpt-5.6-sol"):
            assert get_review_model() == "claude-opus-4-7"


def test_get_review_model_fallback():
    """Test review model fallback to default model."""
    with patch("actions.utils.openai_utils.REVIEW_MODEL", None):
        assert get_review_model() == PR_REVIEW_MODEL_DEFAULT


@patch("requests.post")
def test_get_response(mock_post):
    """Test OpenAI Responses API completion function with mocked response."""
    # Setup mock response with Responses API structure
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 1.5
    mock_response.json.return_value = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Test response from OpenAI"}],
            }
        ]
    }
    mock_post.return_value = mock_response

    # Test with basic messages
    messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

    # Use a context manager for the environment variable
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
            result = get_response(messages, check_links=False)

    assert result == "Test response from OpenAI"
    mock_post.assert_called_once()


@patch("time.sleep")
@patch("requests.post")
def test_get_response_read_timeout_propagates(mock_post, mock_sleep):
    """Test a read timeout is NOT retried: the request may have completed server-side and re-POSTing double-bills."""
    mock_post.side_effect = requests.exceptions.ReadTimeout()

    with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
        try:
            get_response([{"role": "user", "content": "Hello"}], check_links=False, retries=2)
            raise AssertionError("ReadTimeout should propagate")
        except requests.exceptions.ReadTimeout:
            pass
    assert mock_post.call_count == 1  # no re-POST of a possibly-billed request


@patch("time.sleep")
@patch("requests.post")
def test_get_response_retries_rate_limits(mock_post, mock_sleep):
    """Test a 429 response is retried with a longer backoff than server errors."""
    limited = MagicMock()
    limited.status_code = 429
    limited.elapsed.total_seconds.return_value = 0.1
    ok = MagicMock()
    ok.status_code = 200
    ok.elapsed.total_seconds.return_value = 1.0
    ok.json.return_value = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "recovered"}]}]}
    mock_post.side_effect = [limited, ok]

    with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
        result = get_response([{"role": "user", "content": "Hello"}], check_links=False, retries=1)

    assert result == "recovered"
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once_with(10)  # 10 * 2**0, not the 2**0 server-error backoff


@patch("requests.post")
@patch("actions.utils.openai_utils.check_links_in_string")
def test_get_response_with_link_check(mock_check_links, mock_post):
    """Test get_response with link checking."""
    # Setup mocks with Responses API structure
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 2.0
    mock_response.json.return_value = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Response with https://example.com link"}],
            }
        ]
    }
    mock_post.return_value = mock_response
    mock_check_links.return_value = (True, [])

    messages = [{"role": "user", "content": "Hello"}]

    # Use a context manager for the environment variable
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
            result = get_response(messages)

    assert result == "Response with https://example.com link"
    mock_check_links.assert_called_once()


@patch("requests.post")
def test_get_agent_response_calls_function_tools(mock_post):
    """Test iterative Responses API agent calls local tools and returns structured output."""
    first_response = MagicMock()
    first_response.status_code = 200
    first_response.elapsed.total_seconds.return_value = 1.0
    first_response.json.return_value = {
        "id": "resp_first",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_123",
                "name": "lookup_value",
                "arguments": '{"value": "abc"}',
            }
        ],
        "usage": {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 4}, "output_tokens": 5},
    }
    second_response = MagicMock()
    second_response.status_code = 200
    second_response.elapsed.total_seconds.return_value = 1.0
    second_response.json.return_value = {
        "id": "resp_second",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"comments": [], "summary": "done"}'}],
            }
        ],
        "usage": {"input_tokens": 20, "input_tokens_details": {"cached_tokens": 8}, "output_tokens": 7},
    }
    mock_post.side_effect = [first_response, second_response]

    schema = {
        "type": "object",
        "properties": {"comments": {"type": "array"}, "summary": {"type": "string"}},
        "required": ["comments", "summary"],
        "additionalProperties": False,
    }
    tools = [
        {
            "type": "function",
            "name": "lookup_value",
            "description": "Lookup a value.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]

    with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
        with patch("builtins.print") as mock_print:
            result = get_agent_response(
                [{"role": "user", "content": "review"}],
                tools=tools,
                tool_handlers={"lookup_value": lambda value: {"found": value}},
                text_format={"format": {"type": "json_schema", "name": "review", "strict": True, "schema": schema}},
                retries=0,
            )

    assert result == {"comments": [], "summary": "done"}
    assert mock_post.call_count == 2
    first_payload = mock_post.call_args_list[0].kwargs["json"]
    assert first_payload["store"] is True
    assert first_payload["reasoning"] == {"effort": "low"}
    assert "include" not in first_payload
    assert "previous_response_id" not in first_payload
    assert first_payload["input"] == [{"role": "user", "content": "review"}]
    assert mock_post.call_args_list[1].kwargs["json"]["previous_response_id"] == "resp_first"
    second_input = mock_post.call_args_list[1].kwargs["json"]["input"]
    assert second_input == [
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": '{"found": "abc"}',
        }
    ]
    printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    assert "turn 1/6, 1 tools (lookup_value)" in printed
    assert "turn 2/6, 0 tools" in printed
    assert "30→12 tokens (40% cached), $0.00046" in printed
    assert "agent total, 2 turns, 1 tools (lookup_value)" in printed
    assert "Agent tool turn" not in printed  # tool names live in the per-turn usage line now


@patch("requests.post")
def test_get_agent_response_summarizes_after_max_turns(mock_post):
    """Test max-turn exhaustion makes a final no-tool synthesis call."""
    tool_response = MagicMock()
    tool_response.status_code = 200
    tool_response.elapsed.total_seconds.return_value = 1.0
    tool_response.json.return_value = {
        "id": "resp_tool",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_123",
                "name": "lookup_value",
                "arguments": '{"value": "abc"}',
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    final_response = MagicMock()
    final_response.status_code = 200
    final_response.elapsed.total_seconds.return_value = 1.0
    final_response.json.return_value = {
        "id": "resp_final",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"comments": [], "summary": "synthesized"}'}],
            }
        ],
        "usage": {"input_tokens": 20, "output_tokens": 7},
    }
    mock_post.side_effect = [tool_response, requests.exceptions.ConnectTimeout(), final_response]

    schema = {
        "type": "object",
        "properties": {"comments": {"type": "array"}, "summary": {"type": "string"}},
        "required": ["comments", "summary"],
        "additionalProperties": False,
    }
    tools = [
        {
            "type": "function",
            "name": "lookup_value",
            "description": "Lookup a value.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]

    with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
        with patch("actions.utils.openai_utils.time.sleep") as mock_sleep:
            result = get_agent_response(
                [{"role": "user", "content": "review"}],
                tools=tools,
                tool_handlers={"lookup_value": lambda value: f"raw tool output for {value}"},
                text_format={"format": {"type": "json_schema", "name": "review", "strict": True, "schema": schema}},
                max_turns=1,
                retries=0,
            )

    assert result == {"comments": [], "summary": "synthesized"}
    assert mock_post.call_count == 3
    mock_sleep.assert_called_once_with(1)
    final_payload = mock_post.call_args_list[2].kwargs["json"]
    assert final_payload["tools"] == tools
    assert final_payload["tool_choice"] == "none"
    assert final_payload["previous_response_id"] == "resp_tool"
    assert final_payload["input"][0] == {
        "type": "function_call_output",
        "call_id": "call_123",
        "output": "raw tool output for abc",
    }
    assert "Synthesize the gathered tool results" in final_payload["input"][-1]["content"]


@patch("requests.post")
def test_get_response_anthropic(mock_post):
    """Test Anthropic Messages API completion function with mocked response."""
    # Setup mock response with Anthropic Messages API structure
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 1.5
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Test response from Claude"}],
        "usage": {
            "input_tokens": 50,
            "cache_read_input_tokens": 900,
            "cache_creation_input_tokens": 50,
            "output_tokens": 20,
        },
    }
    mock_post.return_value = mock_response

    messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.ANTHROPIC_API_KEY", "test-key"):
            with patch("builtins.print") as mock_print:
                result = get_response(messages, check_links=False, model="claude-sonnet-4-6", background=True)

    assert result == "Test response from Claude"
    printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
    # Cache reads/writes fold into input and reads count as cached, matching ultralytics/assistant normalization
    assert "1000→20 tokens (90% cached), $0.00087" in printed
    mock_post.assert_called_once()
    # Verify Anthropic endpoint was called
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.anthropic.com/v1/messages"


@patch("requests.post")
def test_get_agent_response_stops_at_cost_budget(mock_post):
    """Test the cost budget skips remaining tool turns and forces final synthesis with stub tool outputs."""
    tool_response = MagicMock()
    tool_response.status_code = 200
    tool_response.elapsed.total_seconds.return_value = 1.0
    tool_response.json.return_value = {
        "id": "resp_tool",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_123",
                "name": "lookup_value",
                "arguments": '{"value": "abc"}',
            }
        ],
        "usage": {"input_tokens": 1_000_000, "output_tokens": 0},  # $5.00 for gpt-5.6-sol, over any small budget
    }
    final_response = MagicMock()
    final_response.status_code = 200
    final_response.elapsed.total_seconds.return_value = 1.0
    final_response.json.return_value = {
        "id": "resp_final",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"comments": [], "summary": "budget"}'}],
            }
        ],
        "usage": {"input_tokens": 20, "output_tokens": 7},
    }
    mock_post.side_effect = [tool_response, final_response]

    schema = {
        "type": "object",
        "properties": {"comments": {"type": "array"}, "summary": {"type": "string"}},
        "required": ["comments", "summary"],
        "additionalProperties": False,
    }
    tools = [
        {
            "type": "function",
            "name": "lookup_value",
            "description": "Lookup a value.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]

    def forbidden_handler(value):
        raise AssertionError("tool handlers must not run once the cost budget is reached")

    with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
        result = get_agent_response(
            [{"role": "user", "content": "review"}],
            tools=tools,
            tool_handlers={"lookup_value": forbidden_handler},
            text_format={"format": {"type": "json_schema", "name": "review", "strict": True, "schema": schema}},
            model="gpt-5.6-sol",
            max_turns=8,
            max_cost=1.00,
            retries=0,
        )

    assert result == {"comments": [], "summary": "budget"}
    assert mock_post.call_count == 2  # budget reached on turn 1, remaining turns skipped
    final_payload = mock_post.call_args_list[1].kwargs["json"]
    assert final_payload["tool_choice"] == "none"
    assert final_payload["previous_response_id"] == "resp_tool"
    assert final_payload["input"][0] == {
        "type": "function_call_output",
        "call_id": "call_123",
        "output": "Tool budget exhausted.",
    }
    assert "Synthesize the gathered tool results" in final_payload["input"][-1]["content"]
