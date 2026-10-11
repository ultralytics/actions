# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock, patch

from actions.utils.common_utils import (
    allow_redirect,
    brave_search,
    clean_url,
    remove_html_comments,
)


def test_remove_html_comments():
    """Test removing HTML comments from strings."""
    test_str = "Before <!-- Comment --> After"
    assert remove_html_comments(test_str) == "Before  After"

    # Multiline comment
    test_str = "Before\n<!-- Comment\nline 2\nline 3 -->\nAfter"
    assert remove_html_comments(test_str) == "Before\n\nAfter"

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
    # Should not allow - start ignores
    assert not allow_redirect("https://youtu.be/xyz", "https://youtube.com")

    # Should not allow - git clone URLs
    assert not allow_redirect("https://github.com/ultralytics/ultralytics.git", "https://github.com/ultralytics/yolo")

    # Should not allow - end ignores
    assert not allow_redirect("https://example.com", "https://example.com/404")

    # Empty end URL
    assert not allow_redirect("https://example.com", "")

    # Should allow - GitHub subdomains are not git clone URLs
    assert allow_redirect("https://docs.github.com/en/old", "https://docs.github.com/en/new")
    assert allow_redirect("https://gist.github.com/user/abc", "https://gist.github.com/user/def")

    # Destinations unsafe to bake in, unless the start URL already has the same shape
    assert not allow_redirect("https://hf.test/m/w.pt", "https://cdn.hf.test/w.pt?Expires=9&Signature=ab")  # signed
    assert not allow_redirect("https://youtube.test/ultralytics", "https://consent.youtube.test/m")  # consent wall
    assert not allow_redirect("https://platform.test/deploy", "https://platform.test/signin?next=%2Fdeploy")  # auth
    assert not allow_redirect("https://notion.test/page", "https://app.notion.test/p?session_sync_attempted=1")
    assert not allow_redirect("https://nvidia.test/tensorrt", "https://nvidia.test/en-us/tensorrt")  # locale
    assert not allow_redirect("https://help.test/guide/x", "https://help.test/en-euro/guide/x")  # geo locale
    assert not allow_redirect("https://www.dell.test", "https://www.dell.test/fr-fr")  # locale ending the URL
    assert allow_redirect("https://docs.test/en-gb/old", "https://docs.test/en-gb/new")  # already localized
    assert not allow_redirect("https://blog.test/post", "https://blog.test/post?utm_source=copy_link")  # tracking
    assert allow_redirect("https://blog.test/post?ref=a", "https://blog.test/post-v2?ref=a")  # already tracked
    assert not allow_redirect("https://docs.test/reference/auth", "https://docs.test/reference/auth/auth/key")
    assert allow_redirect("https://docs.test/reference/sdk/sdk/v1", "https://docs.test/reference/sdk/sdk/v2")
    assert allow_redirect("https://github.test/acme/old", "https://github.test/acme/acme")  # owner/repo
    assert not allow_redirect("https://coral.test/projects/x", "https://gweb-coral.uc.r.appspot.com/projects/x")


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
