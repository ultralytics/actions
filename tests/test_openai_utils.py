# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.utils.openai_utils import _is_anthropic_model, get_response, remove_outer_codeblocks


def test_is_anthropic_model():
    """Test model provider detection."""
    assert _is_anthropic_model("claude-sonnet-4-5-20250929") is True
    assert _is_anthropic_model("claude-haiku-4-5-20251001") is True
    assert _is_anthropic_model("claude-opus-4-5-20251101") is True
    assert _is_anthropic_model("gpt-5.2-2025-12-11") is False
    assert _is_anthropic_model("gpt-5-mini-2025-08-07") is False


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
    mock_check_links.return_value = True

    messages = [{"role": "user", "content": "Hello"}]

    # Use a context manager for the environment variable
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
            result = get_response(messages)

    assert result == "Response with https://example.com link"
    mock_check_links.assert_called_once()


@patch("requests.post")
def test_get_response_anthropic(mock_post):
    """Test Anthropic Messages API completion function with mocked response."""
    # Setup mock response with Anthropic Messages API structure
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.elapsed.total_seconds.return_value = 1.5
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Test response from Claude"}],
        "usage": {"input_tokens": 50, "output_tokens": 20},
    }
    mock_post.return_value = mock_response

    messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.ANTHROPIC_API_KEY", "test-key"):
            result = get_response(messages, check_links=False, model="claude-sonnet-4-5-20250929")

    assert result == "Test response from Claude"
    mock_post.assert_called_once()
    # Verify Anthropic endpoint was called
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.anthropic.com/v1/messages"
