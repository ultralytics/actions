# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import asyncio
import os
import re
from urllib import parse

import aiohttp

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

BAD_HTTP_CODES = frozenset({404, 410, 500, 502, 503, 504, 525})

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
    "storage.googleapis.com",
    "{",
    "(",
    "api",
}

URL_PATTERN = re.compile(
    r"\[([^]]+)]\(([^)]+)\)"
    r"|"
    r"("
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:[\w.-]+)?"
    r"\.[a-zA-Z]{2,}"
    r"(?:/[^\s\"')\]<>]*)?"
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


async def brave_search_async(query, api_key, session, count=5):
    """Search for alternative URLs using Brave Search API asynchronously."""
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    if len(query) > 400:
        print(f"WARNING ⚠️ Brave search query length {len(query)} exceed limit of 400 characters, truncating.")
    url = f"https://api.search.brave.com/res/v1/web/search?q={parse.quote(query.strip()[:400])}&count={count}"

    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get("web", {}).get("results", [])
                return [result.get("url") for result in results if result.get("url")]
    except Exception:
        pass

    return []


async def is_url_async(url, session, semaphore, check=True, max_attempts=3, timeout=2):
    """Asynchronously check if string is URL and verify it exists, with GitHub repo handling."""
    try:
        # Check allow list
        if any(x in url for x in URL_IGNORE_LIST):
            return True

        # Check structure
        result = parse.urlparse(url)
        partition = result.netloc.partition(".")
        if not result.scheme or not partition[0] or not partition[2]:
            return False

        if check:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=timeout), "allow_redirects": True}

            async with semaphore:  # Control concurrency
                for attempt in range(max_attempts):
                    try:
                        # Try HEAD first, then GET if needed
                        for method in (session.head, session.get):
                            async with method(url, **kwargs) as response:
                                if response.status not in BAD_HTTP_CODES:
                                    return True

                            # Handle GitHub repos specifically
                            if result.netloc == "github.com" and response.status == 404:
                                parts = result.path.strip("/").split("/")
                                if len(parts) >= 2:
                                    base_url = f"https://github.com/{parts[0]}/{parts[1]}"
                                    async with session.head(base_url, **kwargs) as repo_response:
                                        if repo_response.status == 404:
                                            URL_IGNORE_LIST.add(base_url)
                                            return True

                        return False
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        if attempt == max_attempts - 1:
                            return False
                        await asyncio.sleep(2**attempt)
                return False
        return True
    except Exception:
        return False


async def check_links_in_string_async(text, max_concurrent=50, verbose=True, return_bad=False, replace=False):
    """Asynchronously process text, find unique URLs, check for errors, and optionally replace broken links."""
    all_urls = []
    for md_text, md_url, plain_url in URL_PATTERN.findall(text):
        url = md_url or plain_url
        if url and parse.urlparse(url).scheme:
            all_urls.append((md_text, url, md_url != ""))

    urls = [(t, clean_url(u), is_md) for t, u, is_md in all_urls]  # clean URLs

    # Set up connection pooling with higher limits
    conn = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=10, ttl_dns_cache=300)
    semaphore = asyncio.Semaphore(max_concurrent)

    async with aiohttp.ClientSession(headers=REQUESTS_HEADERS, connector=conn) as session:
        tasks = [is_url_async(url, session, semaphore) for _, url, _ in urls]
        results = await asyncio.gather(*tasks)
        bad_urls = [url for (_, url, _), valid in zip(urls, results) if not valid]

        if replace and bad_urls and (brave_api_key := os.getenv("BRAVE_API_KEY")):
            replacements = {}
            modified_text = text

            # Find replacements for bad URLs
            for (title, url, _), valid in zip(urls, results):
                if not valid:
                    alternative_urls = await brave_search_async(
                        f"{title[:200]} {url[:200]}", brave_api_key, session, count=3
                    )

                    if alternative_urls:
                        # Check each alternative URL
                        for alt_url in alternative_urls:
                            if await is_url_async(alt_url, session, semaphore):
                                replacements[url] = alt_url
                                modified_text = modified_text.replace(url, alt_url)
                                break

            if verbose and replacements:
                print(
                    f"WARNING ⚠️ replaced {len(replacements)} broken links:\n"
                    + "\n".join(f"  {k}: {v}" for k, v in replacements.items())
                )

            if replacements:
                return (True, [], modified_text) if return_bad else modified_text

    passing = not bad_urls
    if verbose and not passing:
        print(f"WARNING ⚠️ errors found in URLs {bad_urls}")

    if replace:
        return (passing, bad_urls, text) if return_bad else text
    return (passing, bad_urls) if return_bad else passing


async def main():
    url = "https://ultralytics.com/images/bus.jpg"
    string = f"This is a string with a [Markdown link]({url}) inside it."

    # Test is_url_async directly
    conn = aiohttp.TCPConnector(limit=50, limit_per_host=10, ttl_dns_cache=300)
    semaphore = asyncio.Semaphore(50)
    async with aiohttp.ClientSession(headers=REQUESTS_HEADERS, connector=conn) as session:
        result = await is_url_async(url, session, semaphore)
        print(f"is_url_async(): {result}")

    # Test check_links_in_string_async
    result = await check_links_in_string_async(string)
    print(f"check_links_in_string_async(): {result}")

    # Test with replace
    result = await check_links_in_string_async(string, replace=True)
    print(f"check_links_in_string_async() with replace: {result}")


if __name__ == "__main__":
    asyncio.run(main())
