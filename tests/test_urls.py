# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# Continuous Integration (CI) GitHub Actions tests

from unittest.mock import patch

import pytest
import requests

from actions.utils.common_utils import allow_redirect, check_links_in_string, is_url, normalize_redirect_url

URLS = [
    "https://docs.ultralytics.com/help/contributing",
    "https://ultralytics.com",
    "https://ultralytics.com/images/bus.jpg",
    "https://github.com/ultralytics/ultralytics",
    # "https://azure.microsoft.com/",  # aggressive bot protections makes Azure links hard to test
    # "https://azure.microsoft.com/en-us/services/machine-learning/",
    # "https://azure.microsoft.com/en-us/products/storage/blobs",
    "https://www.tableau.com/",
    "https://openai.com/research/gpt-4",
    "https://www.reuters.com/article/idUSKCN1MK08G/",
    "https://www.kdnuggets.com/",
    "https://www.datacamp.com/tutorial/understanding-logistic-regression-python",
    "https://www.statisticshowto.com/probability-and-statistics/find-outliers/",
    "https://www.reddit.com/r/Ultralytics/comments/1fw3605/release_megathread/",
    "https://www.kaggle.com/models/ultralytics/yolo11",
    # "https://en.wikipedia.org/wiki/Active_learning_(machine_learning)",  # ends in trailing parenthesis (not working)
    "https://apps.apple.com/xk/app/ultralytics/id1583935240",
]


@pytest.fixture(autouse=True)
def mock_url_checks():
    """Keep URL parsing tests independent of third-party website availability."""

    def fake_is_url(url, session=None, check=True, max_attempts=3, timeout=3, return_url=False, redirect=False):
        valid = url in URLS
        return (valid, url) if return_url else valid

    with patch("actions.utils.common_utils.is_url", side_effect=fake_is_url):
        yield


@pytest.fixture
def verbose():
    """Fixture that provides a verbose logging utility for detailed output during testing and debugging."""
    return False  # Set False to suppress print statements during tests


def test_is_url():
    """Test each URL using is_url function."""
    for url in URLS:
        assert is_url(url, check=False), f"URL check failed: {url}"


def test_links_in_string_func():
    """Test URLs in strings function."""
    assert check_links_in_string(", abc ".join(URLS))


def test_markdown_links_in_string_func():
    """Test Markdown links in strings function."""
    assert check_links_in_string(", abc ".join(f"[text]({url})" for url in URLS))


def test_bracket_links_in_string_func():
    """Test bracket links in strings function."""
    assert check_links_in_string(", abc ".join(f"<{url}>" for url in URLS))


def test_html_links_in_string_func():
    """Test HTML links in strings function."""
    assert check_links_in_string(", abc ".join(f'<a href="{url}">text</a>' for url in URLS))


def test_html_links(verbose):
    """Tests the validity of URLs within HTML anchor tags and returns any invalid URLs found."""
    text = "Visit <a href='https://err.com'>our site</a>, or <a href=\"http://test.org\">test site</a>?"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"https://err.com", "http://test.org"}


def test_markdown_links(verbose):
    """Validates URLs in Markdown links within a given text using check_links_in_string."""
    text = "Check [Example](https://err.com/), or [Test](http://test.org)?"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"https://err.com/", "http://test.org"}


def test_mixed_formats(verbose):
    """Tests URL detection in mixed text formats (HTML, Markdown, plain text) using check_links_in_string."""
    text = "A <a href='https://1.com'>link</a> and [markdown](https://2.org/) and https://3.net"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"https://1.com", "https://2.org/", "https://3.net"}


def test_duplicate_urls(verbose):
    """Tests detection of duplicate URLs in various text formats using the check_links_in_string function."""
    text = "Same URL: https://err.com and <a href='https://err.com'>link</a>"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"https://err.com"}


def test_no_urls(verbose):
    """Tests that a string with no URLs returns True when checked using the check_links_in_string function."""
    text = "This text contains no URLs."
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is True
    assert not set(urls)


def test_invalid_urls(verbose):
    """Test invalid URLs."""
    text = "Invalid URL: http://.com"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"http://.com"}


def test_urls_with_paths_and_queries(verbose):
    """Test URLs with paths and query parameters to ensure they are correctly identified and validated."""
    text = "Complex URL: https://err.com/path?query=value#fragment"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"https://err.com/path?query=value#fragment"}


def test_urls_with_different_tlds(verbose):
    """Test URLs with various top-level domains (TLDs) to ensure correct identification and handling."""
    text = "Different TLDs: https://err.ml https://err.eu https://err.net https://err.io https://err.ai"
    valid_urls = {"https://err.net"}

    def fake_is_url(url, session=None, check=True, max_attempts=3, timeout=3, return_url=False, redirect=False):
        valid = url in valid_urls
        return (valid, url) if return_url else valid

    with patch("actions.utils.common_utils.is_url", side_effect=fake_is_url) as mock_is_url:
        result, urls = check_links_in_string(text, verbose, return_bad=True)

    assert result is False
    assert set(urls) == {"https://err.ml", "https://err.eu", "https://err.io", "https://err.ai"}
    assert mock_is_url.call_count == 5


def test_replace_unlinks_unresolved_links(monkeypatch):
    """Replace dead links a same-site search can fix, unlink the rest, keep inconclusive ones, and never touch code."""
    code = " `https://site.test/bad` and\n```python\nbase = 'https://site.test/gone'\n```"
    links = "[Broken](https://site.test/bad) and [Fixed](https://site.test/gone) and [Flaky](https://site.test/flaky)"
    text = links + " and https://site.test/gone/deeper" + code
    live = {"https://new.test/page", "https://site.test/moved", "https://site.test/gone/deeper"}

    def fake_is_url(url, session=None, check=True, max_attempts=3, timeout=3, return_url=False, redirect=False):
        valid = None if url.endswith("flaky") else url in live
        return (valid, url) if return_url else valid

    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    with patch("actions.utils.common_utils.is_url", side_effect=fake_is_url), patch(
        "actions.utils.common_utils.brave_search",
        side_effect=lambda query, *_, **__: (
            [] if "Broken" in query else ["https://new.test/page", "https://site.test/moved"]
        ),
    ):
        result = check_links_in_string(text, verbose=False, return_bad=True, replace=True)

    fixed = "Broken and [Fixed](https://site.test/moved) and [Flaky](https://site.test/flaky)"
    assert result == (
        False,
        ["https://site.test/bad", "https://site.test/flaky"],
        fixed + " and https://site.test/gone/deeper" + code,
    )


@pytest.mark.parametrize(
    ("start", "end", "allowed"),
    [
        ("https://hf.test/m/resolve/main/w.pt", "https://cdn.hf.test/w.pt?Expires=9&Signature=ab", False),  # signed
        ("https://youtube.test/ultralytics", "https://consent.youtube.test/m?continue=x&gl=ES", False),  # consent
        ("https://youtube.test/ultralytics", "https://consent.youtube.test/m", False),  # bare consent host, no query
        ("https://platform.test/deploy", "https://platform.test/signin?redirect_url=%2Fdeploy", False),  # auth page
        ("https://notion.test/page", "https://app.notion.test/p/page?session_sync_attempted=1", False),  # session
        ("https://nvidia.test/tensorrt", "https://nvidia.test/en-us/tensorrt", False),  # locale inserted
        ("https://docs.test/en/guide", "https://docs.test/en/guide-v2", True),  # source is already localized
        ("https://blog.test/post", "https://blog.test/post?utm_source=copy_link", False),  # tracking added
        ("https://blog.test/post?ref=a", "https://blog.test/post-v2?ref=a", True),  # source already had ref=
        ("https://docs.test/reference/auth", "https://docs.test/reference/auth/auth/key", False),  # segment doubled
        ("https://docs.test/reference/sdk/sdk/v1", "https://docs.test/reference/sdk/sdk/v2", True),  # source doubled
        ("https://github.test/acme/old", "https://github.test/acme/acme", True),  # owner/repo, not an anomaly
        ("https://old.test/deep", "https://old.test/", False),  # deep link collapsing to a homepage
        ("https://root.test", "https://www.root.test/", True),  # homepage to homepage
        ("https://blog.test/post", "https://blog.test/post/", False),  # trailing slash only
        ("https://blog.test/post", "http://blog.test/post-v2", False),  # https downgrade
        ("https://help.test/guide/x", "https://help.test/en-euro/guide/x", False),  # geo locale inserted
        ("https://coral.test/projects/x", "https://gweb-coral.uc.r.appspot.com/projects/x", False),  # hosting origin
    ],
)
def test_allow_redirect_rejects_unsafe_destinations(start, end, allowed):
    """Redirect and search-replacement destinations that are unsafe to bake in are rejected."""
    assert bool(allow_redirect(start=start, end=end)) is allowed


def test_normalize_redirect_url_removes_ultralytics_trailing_slashes():
    """Ultralytics redirect destinations lose their trailing slash; other hosts keep theirs."""
    assert normalize_redirect_url("https://www.ultralytics.com/") == "https://www.ultralytics.com"
    assert normalize_redirect_url("https://docs.ultralytics.com/modes/track/?h=track") == (
        "https://docs.ultralytics.com/modes/track?h=track"
    )
    assert normalize_redirect_url("https://example.com/page/") == "https://example.com/page/"


def test_is_url_falls_back_to_get_and_flags_homepage_collapse():
    """HEAD hangs fall back to GET, homepage collapses and 404s are dead, and unreachable or 5xx URLs are inconclusive."""

    class Response:
        def __init__(self, url, history, status_code=200):
            self.url, self.status_code, self.history = url, status_code, history

        def close(self):
            pass

    class Session:
        def __init__(self, final_url):
            self.final_url = final_url

        def head(self, url, **kwargs):
            raise requests.Timeout

        def get(self, url, **kwargs):
            if self.final_url is None:
                raise requests.ConnectionError
            status = {"https://site.test/gone": 404, "https://site.test/busy": 503}.get(url, 200)
            return Response(self.final_url, [url] if self.final_url != url else [], status)

    assert is_url("https://site.test/page", session=Session("https://site.test/page"))
    assert is_url("https://site.test/page", session=Session("https://site.test/"), return_url=True) == (
        False,
        "https://site.test/",
    )
    assert is_url("https://site.test/gone", session=Session("https://site.test/gone")) is False
    assert is_url("https://site.test/busy", session=Session("https://site.test/busy")) is None
    assert is_url("https://site.test/page", session=Session(None), max_attempts=1) is None


def test_case_sensitivity(verbose):
    """Tests URL case sensitivity by verifying that URLs with different cases are correctly identified and handled."""
    text = "Case test: HTTPS://err.com and https://err.com"
    result, urls = check_links_in_string(text, verbose, return_bad=True)
    assert result is False
    assert set(urls) == {"https://err.com"}
