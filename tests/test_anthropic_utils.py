# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.utils.anthropic_utils import get_response


@patch("requests.post")
def test_get_response(mock_post):
    """Test Anthropic Messages API completion function with mocked response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 1.5
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Test response from Anthropic"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    mock_post.return_value = mock_response

    messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.anthropic_utils.ANTHROPIC_API_KEY", "test-key"):
            result = get_response(messages, check_links=False)

    assert result == "Test response from Anthropic"
    mock_post.assert_called_once()


@patch("requests.post")
@patch("actions.utils.anthropic_utils.check_links_in_string")
def test_get_response_with_link_check(mock_check_links, mock_post):
    """Test get_response with link checking."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 2.0
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Response with https://example.com link"}],
        "usage": {"input_tokens": 10, "output_tokens": 8},
    }
    mock_post.return_value = mock_response
    mock_check_links.return_value = True

    messages = [{"role": "user", "content": "Hello"}]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.anthropic_utils.ANTHROPIC_API_KEY", "test-key"):
            result = get_response(messages)

    assert result == "Response with https://example.com link"
    mock_check_links.assert_called_once()


@patch("requests.post")
def test_get_response_structured_output(mock_post):
    """Test get_response with structured JSON output."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 1.0
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": '{"greeting": "Hello", "mood": "happy"}'}],
        "usage": {"input_tokens": 15, "output_tokens": 10},
    }
    mock_post.return_value = mock_response

    messages = [{"role": "user", "content": "Generate greeting"}]
    schema = {"type": "object", "properties": {"greeting": {"type": "string"}, "mood": {"type": "string"}}}
    text_format = {"format": {"type": "json_schema", "name": "test", "strict": True, "schema": schema}}

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.anthropic_utils.ANTHROPIC_API_KEY", "test-key"):
            result = get_response(messages, text_format=text_format, check_links=False)

    assert isinstance(result, dict)
    assert result["greeting"] == "Hello"
    assert result["mood"] == "happy"


@patch("requests.post")
def test_get_response_with_reasoning_effort(mock_post):
    """Test get_response with reasoning_effort mapped to thinking budget."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 3.0
    mock_response.json.return_value = {
        "content": [{"type": "thinking", "thinking": "Let me think..."}, {"type": "text", "text": "Answer: 42"}],
        "usage": {"input_tokens": 20, "output_tokens": 15},
    }
    mock_post.return_value = mock_response

    messages = [{"role": "user", "content": "What is the meaning of life?"}]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.anthropic_utils.ANTHROPIC_API_KEY", "test-key"):
            result = get_response(messages, reasoning_effort="low", check_links=False)

    assert result == "Answer: 42"
    call_args = mock_post.call_args
    assert "thinking" in call_args.kwargs["json"]
    assert call_args.kwargs["json"]["thinking"]["budget_tokens"] == 1024
