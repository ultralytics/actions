# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import pytest
from unittest.mock import patch, MagicMock

from actions.utils.common_utils import (
    remove_html_comments,
    clean_url,
    allow_redirect,
    brave_search,
    check_links_in_string,
)


def test_remove_html_comments():
    """Test removing HTML comments from strings."""
    test_str = "Before <!-- Comment --> After"
    assert remove_html_comments(test_str) == "Before  After"

    # Multiline comment
    test_str = "Before\n<!-- Comment\nline 2\nline 3 -->\nAfter"
    assert remove_html_comments(test_str) == "Before\nAfter"

    # No comments
    test_str = "No comments here"
    assert remove_html_comments(test_str) == "No comments here"


def test_clean_url():
    """Test cleaning URL strings."""
    # Test removing quotes and trailing characters
    assert clean_url('"https://example.com"') == "https://example.com"
    assert clean_url("'https://example.com'") == "https://example.com"
    assert clean_url("https://example.com.") == "https://example.com"
    assert clean_url("https://example.com,") == "https://example.com"

    # Test git URLs
    assert clean_url("git+https://github.com/user/repo.git@main") == "https://github.com/user/repo"


def test_allow_redirect():
    """Test allowing URL redirects based on rules."""
    # Should allow
    assert allow_redirect("https://example.com", "https://example.org")

    # Should not allow - start ignores
    assert not allow_redirect("https://youtu.be/xyz", "https://youtube.com")

    # Should not allow - end ignores
    assert not allow_redirect("https://example.com", "https://example.com/404")

    # Empty end URL
    assert not allow_redirect("https://example.com", "")


@patch("requests.get")
def test_brave_search(mock_get):
    """Test Brave search API integration."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {"results": [{"url": "https://example.com"}, {"url": "https://example.org"}]}
    }
    mock_get.return_value = mock_response

    results = brave_search("test query", "test-api-key", count=2)
    assert results == ["https://example.com", "https://example.org"]
    mock_get.assert_called_once()


@patch("actions.utils.common_utils.is_url")
def test_check_links_in_string_replacement(mock_is_url):
    """Test replacing bad URLs in strings."""
    mock_is_url.return_value = (True, "https://fixed.com")

    text = "Check out [this link](https://broken.com)."
    result = check_links_in_string(text, verbose=False, replace=True)

    assert "https://fixed.com" in result
    assert "https://broken.com" not in result
