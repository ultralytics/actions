from actions.utils.common_utils import is_url

URLS = [
    'https://docs.ultralytics.com/help/CLA/',
    'https://docs.ultralytics.com/help/contributing',
    'https://docs.ultralytics.com',
    'https://docs.ultralytics.com/help/CI/'
]


def test_urls():
    """Test each URL using is_url function."""
    for url in URLS:
        assert is_url(url), f"URL check failed: {url}"
