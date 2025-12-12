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
