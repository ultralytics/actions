from actions.utils.common_utils import is_url

URLS = [
    "https://docs.ultralytics.com/help/contributing",
    "https://github.com/ultralytics/ultralytics",
]


def test_is_url():
    """Test each URL using is_url function."""
    for url in URLS:
        assert is_url(url), f"URL check failed: {url}"


def test_markdown_links():
    """Test Markdown link detection."""
    text = "[Link](https://docs.ultralytics.com) and [Another](https://docs.ultralytics.com/help/CI/)."
    result, bad = check_links_in_string(text, verbose=False, return_bad=True)
    assert result
    assert not bad


def test_plaintext_links():
    """Test plaintext URL detection."""
    text = "Visit https://docs.ultralytics.com. And also visit https://docs.ultralytics.com/help/CI/."
    result = check_links_in_string(text, verbose=False)
    assert result


def test_mixed_format_links():
    """Test mixed format URL detection."""
    text = "<a href='https://github.com'>Link</a> and [Doc](https://github.com/help/CI/) and https://github.com"
    assert check_links_in_string(text, verbose=False)


def test_invalid_links():
    """Test invalid URL handling."""
    text = "Visit https://invalid.nonexistent.url.com"
    result, bad = check_links_in_string(text, verbose=False, return_bad=True)
    assert not result
    assert bad
