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


@patch("requests.post")
def test_get_completion_with_github_token(mock_post):
    """Test GitHub Models API completion function with mocked response."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "Test response from GitHub Models"}}]}
    mock_post.return_value = mock_response

    # Test with basic messages
    messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

    # Use GitHub token instead of OpenAI API key
    with patch.dict("os.environ", {"GITHUB_TOKEN": "test-github-token"}, clear=True):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", None):
            with patch("actions.utils.openai_utils.GITHUB_TOKEN", "test-github-token"):
                result = get_completion(messages, check_links=False)

    assert result == "Test response from GitHub Models"
    mock_post.assert_called_once()
    
    # Verify the correct URL and headers were used for GitHub Models
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://models.github.ai/inference/chat/completions"
    assert "Bearer test-github-token" in call_args[1]["headers"]["Authorization"]
    
    # Verify model name is prefixed with "openai/"
    data = call_args[1]["json"]
    assert data["model"].startswith("openai/")


def test_get_completion_no_credentials():
    """Test that get_completion raises error when no credentials are available."""
    messages = [{"role": "user", "content": "Hello"}]
    
    # Test with no credentials
    with patch.dict("os.environ", {}, clear=True):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", None):
            with patch("actions.utils.openai_utils.GITHUB_TOKEN", None):
                try:
                    get_completion(messages, check_links=False)
                    assert False, "Expected AssertionError to be raised"
                except AssertionError as e:
                    assert "Either OpenAI API key or GitHub token is required" in str(e)


@patch("requests.post")
def test_get_completion_openai_preferred_over_github(mock_post):
    """Test that OpenAI API is preferred when both credentials are available."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
    mock_post.return_value = mock_response

    messages = [{"role": "user", "content": "Hello"}]

    # Test with both credentials available
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-openai-key", "GITHUB_TOKEN": "test-github-token"}, clear=True):
        with patch("actions.utils.openai_utils.OPENAI_API_KEY", "test-openai-key"):
            with patch("actions.utils.openai_utils.GITHUB_TOKEN", "test-github-token"):
                result = get_completion(messages, check_links=False)

    # Verify OpenAI API was used (not GitHub Models)
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.openai.com/v1/chat/completions"
    assert "Bearer test-openai-key" in call_args[1]["headers"]["Authorization"]
