# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import parse

import requests

# Common directories to exclude when traversing file trees (used by the Python docstring formatter)
COMMON_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".nox",
        ".eggs",
        "eggs",
        ".idea",
        ".vscode",
        "node_modules",
        "site-packages",
        "build",
        "dist",
    }
)

# Patterns for files that should be skipped in PR summaries and reviews (lock files, generated, minified, etc.)
SKIP_PATTERN_STRINGS = [
    r"\.lock$",  # Lock files
    r"-lock\.(json|yaml|yml)$",
    r"\.min\.(js|css)$",  # Minified
    r"\.bundle\.(js|css)$",
    r"(^|/)dist/",  # Generated/vendored directories
    r"(^|/)build/",
    r"(^|/)vendor/",
    r"(^|/)node_modules/",
    r"(^|/)coverage/",  # Coverage reports
    r"\.pb\.py$",  # Proto generated
    r"_pb2\.py$",
    r"_pb2_grpc\.py$",
    r"^package-lock\.json$",  # Package locks
    r"^yarn\.lock$",
    r"^poetry\.lock$",
    r"^Pipfile\.lock$",
    r"^uv\.lock$",
    r"\.(svg|png|jpe?g|gif|ico|webp|avif|heic|heif|tiff?|bmp|eps|raw|cr2|nef|arw|dng|psd|ai|xcf)$",  # Images
    r"\.(woff2?|ttf|eot|otf)$",  # Fonts
    r"\.(mp4|webm|mov|avi|mkv|wmv|flv|m4v|3gp|mpeg|mpg|ogv|mts)$",  # Videos
    r"\.(mp3|wav|ogg|flac|aac|m4a|wma|opus|aiff?)$",  # Audio
    r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|odt|ods|odp|rtf|epub)$",  # Documents
    r"\.(zip|tar|gz|tgz|bz2|xz|rar|7z|cab|iso|dmg)$",  # Archives
    r"\.(exe|dll|so|dylib|bin|o|a|lib|pyc|pyo|class|jar|war|whl|egg)$",  # Binaries
    r"\.(db|sqlite|sqlite3|mdb|pkl|pickle|npy|npz|h5|hdf5|parquet|arrow|feather)$",  # Data/Database
    r"\.(pt|pth|onnx|pb|tflite|mlmodel|safetensors|ckpt|weights|model)$",  # ML Models
    r"\.generated\.",  # Common generated file pattern
]
SKIP_PATTERNS = tuple(re.compile(pattern) for pattern in SKIP_PATTERN_STRINGS)

# Regex to extract file path from git diff header (handles quoted paths with spaces/renames)
DIFF_FILE_PATTERN = re.compile(r' "?b/(.+?)"?$')

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
}
ACTIONS_CREDIT = "<sub>Made with ❤️ by [Ultralytics Actions](https://www.ultralytics.com/actions)</sub>"
BAD_HTTP_CODES = frozenset(
    {
        204,  # No content
        # 403,  # Forbidden - client lacks permission to access the resource (commented as works in browser typically)
        404,  # Not Found - requested resource doesn't exist
        405,  # Method Not Allowed - HTTP method not supported for this endpoint
        406,  # Not Acceptable - server can't generate response matching client's acceptable headers
        410,  # Gone - resource permanently removed
        500,  # Internal Server Error - server encountered an error
        502,  # Bad Gateway - upstream server sent invalid response
        503,  # Service Unavailable - server temporarily unable to handle request
        504,  # Gateway Timeout - upstream server didn't respond in time
        525,  # Cloudflare handshake error
    }
)

URL_ERROR_LIST = {  # automatically reject these URLs (important: replace spaces with '%20')
    "https://blog.research.google/search/label/Spam%20and%20Abuse",
    "https://blog.research.google/search/label/Adversarial%20Attacks",
    "https://www.microsoft.com/en-us/security/business/ai-machine-learning-security",
    "https://about.netflix.com/en/news/netflix-recommendations-beyond-the-5-stars-part-1",
    "https://about.netflix.com/en/news/netflix-research-recommendations",
}

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
    "https://x.com",  # do not use just 'x' as this will catch other domains like netflix.com
    "storage.googleapis.com",  # private GCS buckets
    "{",  # possible Python fstring
    "(",  # breaks pattern matches
    ")",
    "api.",  # ignore api endpoints
}
REDIRECT_START_IGNORE_LIST = frozenset(
    {
        "{",  # possible f-string
        "}",  # possible f-string
        "https://youtu.be",
        "bit.ly",
        "ow.ly",
        "shields.io",
        "badge",
        "ultralytics.com/actions",
        "ultralytics.com/bilibili",
        "ultralytics.com/images",
        "ultralytics.com/app-install",
        "ultralytics.com/assets",
        "app.gong.io/call?",
        "docs.openvino.ai",
        ".git",
        "/raw/",  # GitHub images
        ".slack.com",  # Slack URLs to private channels
        "https://maps.app.goo.gl/nxB8YygRQeXSS9G18",  # Ultralytics Madrid office - Cra de San Jeronimo 15
        "https://maps.app.goo.gl/9sdE3KrQVwc2shb86",  # Ultralytics London office - 50 York Way
    }
    | URL_IGNORE_LIST
)
REDIRECT_END_IGNORE_LIST = frozenset(
    {
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
        "latex.codecogs.com",
        "svg.image",
        "?view=azureml",
        "?utm_",
        "redirect",
        "https://code.visualstudio.com/",  # errors
        "?rdt=",  # problems with reddit redirecting to https://www.reddit.com/r/ultralytics/?rdt=48616
        "githubusercontent.com",  # Prevent replacement with temporary signed GitHub asset URLs
    }
)
URL_ALTERNATIVES = (
    r"(?P<image>!?)\[(?P<md_text>[^]]+)]\(\s*(?P<md_url>[^)\s]+)[^)]*\)"  # Matches Markdown links and images
    r"|"
    r"(?P<space>[ \t]?)"  # Optional leading space, dropped along with a removed autolink or plaintext URL
    r"(?:"
    r"<(?P<auto_url>https?://[^<>\s\[\]]+)>"  # Matches Markdown autolinks
    r"|"
    r"(?P<plain_url>"  # Start capturing group for plaintext URLs
    r"(?:https?://)?"  # Optional http:// or https://
    r"(?:www\.)?"  # Optional www.
    r"(?:[\w.-]+)?"  # Optional domain name and subdomains
    r"\.[a-zA-Z]{2,}"  # TLD
    r"(?:/[^\s\"')\]<>]*)?"  # Optional path
    r")"
    r")"
)
URL_PATTERN = re.compile(URL_ALTERNATIVES)  # finds every URL, including inside code samples and HTML attributes
REPLACE_PATTERN = re.compile(  # one pass over the original text: rewrites hyperlinks, leaves URLs that are data
    r"(?:```[\s\S]*?```|`[^`\n]*`)"  # code samples are copied verbatim, never edited
    r"|(?i:"  # HTML anchors, whose text stops at the next <a> so an unclosed tag cannot swallow a later one
    r"(?P<a_open><a\b[^>]*?\shref\s*=\s*)(?P<a_href>\"[^\"]*\"|'[^']*'|[^\s>]*)(?P<a_tail>[^>]*>)"
    r"(?P<a_text>[^<]*(?:<(?!/?a\b)[^<]*)*)</a>)"
    r"|" + URL_ALTERNATIVES + r"|<[^>]+>"  # an HTML attribute URL has no anchor to keep, so leave the tag alone
)


def remove_html_comments(body: str) -> str:
    """Removes HTML comments from a string using regex pattern matching."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip() if body else ""


def should_skip_file(path: str) -> bool:
    """Return True if file path matches a generated/minified skip pattern (lock files, images, etc.)."""
    normalized = Path(path).as_posix()
    normalized = normalized[2:] if normalized.startswith("./") else normalized
    filename = normalized.rsplit("/", 1)[-1]
    return any(pattern.search(candidate) for pattern in SKIP_PATTERNS for candidate in (normalized, filename))


def filter_diff_text(diff_text: str) -> tuple[str, list[str]]:
    """Filter diff text to exclude lock files and other generated files.

    Returns:
        tuple: (filtered_diff_text, list of skipped file paths)
    """
    if not diff_text or diff_text.startswith("ERROR"):
        return diff_text, []

    filtered_lines = []
    skipped_files = set()
    current_file = None
    skip_current = False

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Extract file path from diff header using shared pattern
            if match := DIFF_FILE_PATTERN.search(line):
                current_file = match.group(1).rstrip('"')
            else:
                current_file = None
            skip_current = current_file and should_skip_file(current_file)

            if skip_current and current_file:
                skipped_files.add(current_file)
            else:
                filtered_lines.append(line)
        elif skip_current:
            continue
        else:
            filtered_lines.append(line)

    return "\n".join(filtered_lines), sorted(skipped_files)


def format_skipped_files_dropdown(skipped_files: list[str], max_files: int = 100) -> str:
    """Format skipped files as a collapsible HTML details dropdown for GitHub Markdown."""
    if not skipped_files:
        return ""
    count = len(skipped_files)
    summary = f"📋 Skipped {count} file{'s' if count != 1 else ''} (lock files, generated, images, etc.)"
    file_list = "\n".join(f"- `{f}`" for f in sorted(skipped_files)[:max_files])
    if count > max_files:
        file_list += f"\n- ... and {count - max_files} more"
    return f"\n<details><summary>{summary}</summary>\n\n{file_list}\n</details>\n"


def format_skipped_files_note(skipped_files: list[str], max_files: int = 10) -> str:
    """Format skipped files as a brief inline note for AI prompts."""
    if not skipped_files:
        return ""
    note = "\n\nNote: The following auto-generated/lock files were also modified but diff details omitted: "
    note += ", ".join(f"`{f}`" for f in skipped_files[:max_files])
    if len(skipped_files) > max_files:
        note += f" and {len(skipped_files) - max_files} more"
    return note


def clean_url(url):
    """Remove extra characters from URL strings."""
    url = str(url).strip().strip('"').strip("'").rstrip(".,:;!?`\\").replace(".git@main", "").replace("git+", "")
    # Second pass for nested quotes/punctuation/whitespace, i.e. HTML href=" 'https://url.com' "
    url = url.strip().strip('"').strip("'").rstrip(".,:;!?`\\")
    return url


def allow_redirect(start="", end=""):
    """Check if a redirect target should be applied based on simple allow rules."""
    start_lower = start.lower()
    end_lower = end.lower()
    return (
        end
        and end.startswith("https://")
        and all(item not in end_lower for item in REDIRECT_END_IGNORE_LIST)
        and all(item not in start_lower for item in REDIRECT_START_IGNORE_LIST)
    )


def brave_search(query, api_key, count=5):
    """Search for alternative URLs using Brave Search API, returning None if the search itself did not answer."""
    if not api_key:
        return None
    if len(query) > 400:
        print(f"WARNING ⚠️ Brave search query length {len(query)} exceed limit of 400 characters, truncating.")
    url = f"https://api.search.brave.com/res/v1/web/search?q={parse.quote(query.strip()[:400])}&count={count}"
    try:
        response = requests.get(
            url, headers={"X-Subscription-Token": api_key, "Accept": "application/json"}, timeout=10
        )
        if response.status_code == 200:
            return [r["url"] for r in response.json().get("web", {}).get("results", []) if r.get("url")]
        print(f"WARNING ⚠️ Brave search HTTP {response.status_code}")
    except Exception as e:
        print(f"WARNING ⚠️ Brave search failed: {e}")
    return None  # rate limited or unreachable, which is not the same as "no replacement exists"


def is_url(url, session=None, check=True, max_attempts=3, timeout=3, return_url=False, redirect=False):
    """Check if string is URL and optionally verify it exists, with fallback for GitHub repos."""
    try:
        # Check allow list
        if any(x in url for x in URL_IGNORE_LIST):
            return (True, url) if return_url else True

        # Check structure
        result = parse.urlparse(url)
        partition = result.netloc.partition(".")  # i.e. netloc = "github.com" -> ("github", ".", "com")
        if not result.scheme or not partition[0] or not partition[2] or (url in URL_ERROR_LIST):
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
                        # Only update URL if there were actual HTTP redirects (indicated by response.history)
                        if redirect and response.history and allow_redirect(start=url, end=response.url):
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
    """Process text, find URLs, check for 404s, and replace or remove the broken ones."""
    urls = []
    for match in URL_PATTERN.finditer(text):
        url = clean_url(match["md_url"] or match["auto_url"] or match["plain_url"] or "")
        if url and parse.urlparse(url).scheme:
            urls.append((match["md_text"] or "", url))

    with requests.Session() as session, ThreadPoolExecutor(max_workers=64) as executor:
        session.headers.update(REQUESTS_HEADERS)
        session.cookies = requests.cookies.RequestsCookieJar()
        results = list(executor.map(lambda x: is_url(x[1], session, return_url=True, redirect=True), urls))
        bad_urls = [url for (title, url), (valid, redirect) in zip(urls, results) if not valid]

        if replace:
            link_actions = {}  # {url: replacement URL, or None to remove the link and keep its anchor text}
            brave_api_key = os.getenv("BRAVE_API_KEY")
            for (title, url), (valid, redirect) in zip(urls, results):
                if url in link_actions:  # decide once per URL, not once per occurrence
                    continue
                if not valid:
                    # Two distinct queries, not two attempts: the dead URL biases the first toward the site root,
                    # so the second drops it and searches the link text on the same domain instead.
                    best, answered = None, False
                    for query in (
                        f"{(redirect or url)[:200]} {title[:199]}",
                        f"{title[:199]} {parse.urlparse(url).netloc}",
                    ):
                        if (search_urls := brave_search(query, brave_api_key, count=3)) is None:
                            continue  # search did not answer; a silent [] here would delete a fixable link
                        answered = True
                        if best := next((u for u in search_urls if u != url and is_url(u, session)), None):
                            break
                    if best or answered:  # leave the link untouched when no search ever answered
                        link_actions[url] = best
                elif redirect and redirect != url:
                    link_actions[url] = redirect

            if verbose and link_actions:
                print(
                    f"WARNING ⚠️ updated {len(link_actions)} links:\n"
                    + "\n".join(f"  {k}: {v or 'REMOVED'}" for k, v in link_actions.items())
                )

            handled = set()  # URLs this pass actually rewrote or removed, the only ones it may certify as gone

            def replace_link(match):
                """Point a matched link at its replacement URL, or remove it and retain any readable text."""
                if match["a_text"] is not None:  # HTML anchor: keep the content, then rewrite or unwrap the tags
                    content = REPLACE_PATTERN.sub(replace_link, match["a_text"])
                    href, url = match["a_href"], clean_url(match["a_href"])
                    if url not in link_actions:
                        return f"{match['a_open']}{href}{match['a_tail']}{content}</a>"
                    handled.add(url)
                    if not (new_url := link_actions[url]):
                        return content
                    quote = href[0] if href.startswith(('"', "'")) else ""
                    return f"{match['a_open']}{quote}{new_url}{quote}{match['a_tail']}{content}</a>"
                raw_url = match["md_url"] or match["auto_url"] or match["plain_url"] or ""
                url = clean_url(raw_url)
                if url not in link_actions:
                    return match[0]
                handled.add(url)
                new_url = link_actions[url]
                if match["md_url"]:
                    md_text = REPLACE_PATTERN.sub(replace_link, match["md_text"])  # text may repeat the same URL
                    return f"{match['image']}[{md_text}]({new_url})" if new_url else md_text
                if match["auto_url"]:
                    return f"{match['space']}<{new_url}>" if new_url else ""
                suffix = raw_url[len(raw_url.rstrip(".,:;!?`\\")) :]  # trailing punctuation clean_url() dropped
                return f"{match['space']}{new_url}{suffix}" if new_url else suffix

            text = REPLACE_PATTERN.sub(replace_link, text)
            bad_urls = [url for url in bad_urls if url not in handled]  # a URL left as data is still a bad URL

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
