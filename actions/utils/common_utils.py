# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib import parse

import requests

REQUESTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8,zh-CN;q=0.7,zh;q=0.6",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "sec-ch-ua": '"Chromium";v="132", "Google Chrome";v="132", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com/",
}
BAD_HTTP_CODES = frozenset(
    {
        # 204,  # No content
        # 403,  # Forbidden - client lacks permission to access the resource (commented as works in browser typically)
        404,  # Not Found - requested resource doesn't exist
        405,  # Method Not Allowed - HTTP method not supported for this endpoint
        410,  # Gone - resource permanently removed
        500,  # Internal Server Error - server encountered an error
        502,  # Bad Gateway - upstream server sent invalid response
        503,  # Service Unavailable - server temporarily unable to handle request
        504,  # Gateway Timeout - upstream server didn't respond in time
        525,  # Cloudfare handshake error
    }
)
URL_IGNORE_LIST = {  # use a set (not frozenset) to update with possible private GitHub repos
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
    "linkedin.com",
    "twitter.com",
    "x.com",
    "storage.googleapis.com",  # private GCS buckets
    "{",  # possible Python fstring
    "(",  # breaks pattern matches
    "api.",  # ignore api endpoints
}
REDIRECT_IGNORE_LIST = frozenset(
    {
        "{",  # possible f-string
        "}",  # possible f-string
        "/es/",
        "/us/",
        "en-us",
        "es-es",
        "/latest/",
        ":text",  # ignore text-selection links due to parsing complications
        ":443",  # https://getcruise.com/ -> https://www.gm.com:443/innovation/path-to-autonomous
        "404",
        "notfound",
        "unsupported",  # https://labs.google/fx/tools/video-fx/unsupported-country
        "authorize",  # nature articles like https://idp.nature.com/authorize?response_type=cookie&client...
        "credential",
        "login",
        "consent",
        "verify",
        "badge",
        "shields.io",
        "bit.ly",
        "ow.ly",
        "https://youtu.be/",
        "latex.codecogs.com",
        "svg.image",
        "?view=azureml",
        "?utm_",
        "redirect",
        "ultralytics.com/actions",
        "ultralytics.com/bilibili",
        "ultralytics.com/images",
        "app.gong.io/call?",
        "https://code.visualstudio.com/",  # errors
        "?rdt=",  # problems with reddit redirecting to https://www.reddit.com/r/ultralytics/?rdt=48616
        "objects.githubusercontent.com",  # Prevent replacement with temporary signed GitHub asset URLs
    }
)
URL_PATTERN = re.compile(
    r"\[([^]]+)]\(([^)]+)\)"  # Matches Markdown links [text](url)
    r"|"
    r"("  # Start capturing group for plaintext URLs
    r"(?:https?://)?"  # Optional http:// or https://
    r"(?:www\.)?"  # Optional www.
    r"(?:[\w.-]+)?"  # Optional domain name and subdomains
    r"\.[a-zA-Z]{2,}"  # TLD
    r"(?:/[^\s\"')\]<>]*)?"  # Optional path
    r")"
)


def remove_html_comments(body: str) -> str:
    """Removes HTML comments from a string using regex pattern matching."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()


def clean_url(url):
    """Remove extra characters from URL strings."""
    for _ in range(3):
        url = str(url).strip('"').strip("'").rstrip(".,:;!?`\\").replace(".git@main", "").replace("git+", "")
    return url


def allow_redirect(url):
    """Check if URL should be skipped based on simple rules."""
    url_lower = url.lower()
    return url and url.startswith("https://") and not any(item in url_lower for item in REDIRECT_IGNORE_LIST)


def brave_search(query, api_key, count=5):
    """Search for alternative URLs using Brave Search API."""
    if not api_key:
        return
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    if len(query) > 400:
        print(f"WARNING ⚠️ Brave search query length {len(query)} exceed limit of 400 characters, truncating.")
    url = f"https://api.search.brave.com/res/v1/web/search?q={parse.quote(query.strip()[:400])}&count={count}"
    response = requests.get(url, headers=headers)
    data = response.json() if response.status_code == 200 else {}
    results = data.get("web", {}).get("results", []) if data else []
    return [result.get("url") for result in results if result.get("url")]


def is_url(url, session=None, check=True, max_attempts=3, timeout=2, return_url=False, redirect=False):
    """Check if string is URL and optionally verify it exists, with fallback for GitHub repos."""
    try:
        # Check allow list
        if any(x in url for x in URL_IGNORE_LIST):
            return (True, url) if return_url else True

        # Check structure
        result = parse.urlparse(url)
        partition = result.netloc.partition(".")  # i.e. netloc = "github.com" -> ("github", ".", "com")
        if not result.scheme or not partition[0] or not partition[2]:
            return (False, url) if return_url else False

        if check:
            requester = session or requests
            kwargs = {"timeout": timeout, "allow_redirects": True}
            if not session:
                kwargs["headers"] = REQUESTS_HEADERS

            for attempt in range(max_attempts):
                try:
                    # Try HEAD first, then GET if needed
                    for method in (requester.head, requester.get):
                        response = method(url, stream=method == requester.get, **kwargs)
                        if redirect and allow_redirect(response.url):
                            url = response.url
                        if response.status_code not in BAD_HTTP_CODES:
                            return (True, url) if return_url else True

                        # If GitHub and check fails (repo might be private), add the base GitHub URL to ignore list
                        if result.hostname == "github.com":
                            parts = result.path.strip("/").split("/")
                            if len(parts) >= 2:
                                base_url = f"https://github.com/{parts[0]}/{parts[1]}"  # https://github.com/org/repo
                                if requester.head(base_url, **kwargs).status_code == 404:
                                    URL_IGNORE_LIST.add(base_url)
                                    return (True, url) if return_url else True

                    return (False, url) if return_url else False
                except Exception:
                    if attempt == max_attempts - 1:  # last attempt
                        return (False, url) if return_url else False
                    time.sleep(2**attempt)  # exponential backoff
            return (False, url) if return_url else False
        return (True, url) if return_url else True
    except Exception:
        return (False, url) if return_url else False


def check_links_in_string(text, verbose=True, return_bad=False, replace=False):
    """Process text, find URLs, check for 404s, and handle replacements with redirects or Brave search."""
    urls = []
    for md_text, md_url, plain_url in URL_PATTERN.findall(text):
        url = md_url or plain_url
        if url and parse.urlparse(url).scheme:
            urls.append((md_text, clean_url(url)))

    with requests.Session() as session, ThreadPoolExecutor(max_workers=64) as executor:
        session.headers.update(REQUESTS_HEADERS)
        results = list(executor.map(lambda x: is_url(x[1], session, return_url=True, redirect=True), urls))
        bad_urls = [url for (title, url), (valid, redirect) in zip(urls, results) if not valid]

        if replace:
            replacements = {}
            modified_text = text

            # Process all URLs for replacements
            brave_api_key = os.getenv("BRAVE_API_KEY")
            for (title, url), (valid, redirect) in zip(urls, results):
                # Handle invalid URLs with Brave search
                if not valid and brave_api_key:
                    if search_urls := brave_search(f"{title[:200]} {(redirect or url)[:200]}", brave_api_key, count=3):
                        best_url = search_urls[0]
                        for alt_url in search_urls:
                            if is_url(alt_url, session):
                                best_url = alt_url
                                break
                        replacements[url] = best_url
                        modified_text = modified_text.replace(url, best_url)
                # Handle redirects for valid URLs
                elif valid and redirect and redirect != url:
                    replacements[url] = redirect
                    modified_text = modified_text.replace(url, redirect)

            if verbose and replacements:
                print(
                    f"WARNING ⚠️ replaced {len(replacements)} links:\n"
                    + "\n".join(f"  {k}: {v}" for k, v in replacements.items())
                )
            if replacements:
                return (True, bad_urls, modified_text) if return_bad else modified_text

    passing = not bad_urls
    if verbose and not passing:
        print(f"WARNING ⚠️ errors found in URLs {bad_urls}")

    if replace:
        return (passing, bad_urls, text) if return_bad else text
    return (passing, bad_urls) if return_bad else passing


if __name__ == "__main__":
    url = "https://ultralytics.com/images/bus.jpg"
    string = f"This is a string with a [Markdown link]({url}) inside it."

    print(f"is_url(): {is_url(url)}")
    print(f"check_links_in_string(): {check_links_in_string(string)}")
    print(f"check_links_in_string() with replace: {check_links_in_string(string, replace=True)}")
