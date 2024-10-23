# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import re
import socket
import time
import urllib
from concurrent.futures import ThreadPoolExecutor


def remove_html_comments(body: str) -> str:
    """Removes HTML comments from a string using regex pattern matching."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()


def clean_url(url):
    """Remove extra characters from URL strings."""
    for _ in range(3):
        url = str(url).strip('"').strip("'").rstrip(".,:;!?`\\").replace(".git@main", "").replace("git+", "")
    return url


def is_url(url, check=True, max_attempts=3, timeout=2):
    """Check if string is URL and check if URL exists."""
    allow_list = (
        "localhost",
        "127.0.0",
        ":5000",
        ":3000",
        ":8000",
        ":8080",
        ":6006",
        "MODEL_ID",
        "API_KEY",
        "url",
        "example",
        "mailto:",
        "github.com",  # ignore GitHub links that may be private repos
        "kaggle.com",  # blocks automated header requests
        "reddit.com",  # blocks automated header requests
    )
    try:
        # Check allow list
        if any(x in url for x in allow_list):
            return True

        # Check structure
        result = urllib.parse.urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False

        # Check response
        if check:
            for attempt in range(max_attempts):
                try:
                    req = urllib.request.Request(
                        url,
                        method="HEAD",
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        return response.getcode() < 400
                except (urllib.error.URLError, socket.timeout):
                    if attempt == max_attempts - 1:  # last attempt
                        return False
                    time.sleep(2**attempt)  # exponential backoff
            return False
        return True
    except Exception:
        return False


def check_links_in_string(text, verbose=True, return_bad=False):
    """Process a given text, find unique URLs within it, and check for any 404 errors."""
    pattern = (
        r"\[([^\]]+)\]\(([^)]+)\)"  # Matches Markdown links [text](url)
        r"|"
        r"("  # Start capturing group for plaintext URLs
        r"(?:https?://)?"  # Optional http:// or https://
        r"(?:www\.)?"  # Optional www.
        r"[\w.-]+"  # Domain name and subdomains
        r"\.[a-zA-Z]{2,}"  # TLD
        r"(?:/[^\s\"')\]]*)?"  # Optional path
        r")"
    )
    all_urls = []
    for md_text, md_url, plain_url in re.findall(pattern, text):
        url = md_url or plain_url
        if url and urllib.parse.urlparse(url).scheme:
            all_urls.append(url)

    urls = set(map(clean_url, all_urls))  # remove extra characters and make unique
    with ThreadPoolExecutor(max_workers=16) as executor:  # multi-thread
        bad_urls = [url for url, valid in zip(urls, executor.map(lambda x: not is_url(x, check=True), urls)) if valid]

    passing = not bad_urls
    if verbose and not passing:
        print(f"WARNING ⚠️ errors found in URLs {bad_urls}")

    return (passing, bad_urls) if return_bad else passing
