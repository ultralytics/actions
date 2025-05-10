# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.utils.openai_utils import get_completion, remove_outer_codeblocks


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
def test_get_completion(mock_post):
    """Test OpenAI API completion function with mocked response."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "Test response from OpenAI"}}]}
    mock_post.return_value = mock_response

    # Test with basic messages
    messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

    # Use a context manager for the environment variable
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
            result = get_completion(messages, check_links=False)

    assert result == "Test response from OpenAI"
    mock_post.assert_called_once()


@patch("requests.post")
@patch("actions.utils.openai_utils.check_links_in_string")
def test_get_completion_with_link_check(mock_check_links, mock_post):
    """Test get_completion with link checking."""
    # Setup mocks
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "Response with https://example.com link"}}]}
    mock_post.return_value = mock_response
    mock_check_links.return_value = True

    messages = [{"role": "user", "content": "Hello"}]

    # Use a context manager for the environment variable
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-key"):
            result = get_completion(messages)

    assert result == "Response with https://example.com link"
    mock_check_links.assert_called_once()
