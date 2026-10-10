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
    r"(^|/)generated/",
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
DEAD_HTTP_CODES = frozenset({404, 410})  # definitive; other bad codes may be transient
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
    # Curated never-link pages: dead, moved, soft 404s, deprecated HUB docs, or sites that block automated checks
    "http://host.robots.ox.ac.uk/pascal/VOC/voc2012/htmldoc/index.html",
    "http://jetson.webredirect.org/jp6/cu126",
    "http://localhost:6006/",
    "http://projectx.saharm.com/",
    "http://v/",
    "http://visualdslab.com/~jpocom/pubs/17KGraffiti2022.pdf",
    "http://www.projectx.saharm.com/",
    "https://albumentations.ai/docs/reference/supported-targets-by-transform/",
    "https://blog.research.google/2019/09/pioneering-differential-privacy-for-all.html",
    "https://blog.research.google/2021/01/introducing-switch-transformers-scaling.html",
    "https://blog.research.google/2021/01/switch-transformers-scaling-to-trillion",
    "https://blog.research.google/2021/01/switch-transformers-scaling-to-trillion.html",
    "https://cloud.google.com/learn/what-is-data-management",
    "https://community.ultralytics.com/u/UltraBot",
    "https://dl.acm.org/doi/10.1145/3442381.3442400",
    "https://docs.neuralmagic.com/use-cases/object-detection/sparsifying?utm_campaign=yolov5_nm_integration&utm_source=ultralytics_blog",
    "https://docs.ray.io/en/latest/serve/tutorials/vllm-example.html",
    "https://docs.ultralytics.com/hub",
    "https://docs.ultralytics.com/hub/app",
    "https://docs.ultralytics.com/hub/cloud-training",
    "https://docs.ultralytics.com/hub/cloud-training#billing",
    "https://docs.ultralytics.com/hub/cloud-training#train-model",
    "https://docs.ultralytics.com/hub/cloud-training?h=cloud",
    "https://docs.ultralytics.com/hub/cloud-training?h=hub+cloud+training",
    "https://docs.ultralytics.com/hub/datasets",
    "https://docs.ultralytics.com/hub/inference-api",
    "https://docs.ultralytics.com/hub/inference-api#dedicated-inference-api",
    "https://docs.ultralytics.com/hub/inference-api#shared-inference-api",
    "https://docs.ultralytics.com/hub/integrations",
    "https://docs.ultralytics.com/hub/integrations#models",
    "https://docs.ultralytics.com/hub/models",
    "https://docs.ultralytics.com/hub/projects",
    "https://docs.ultralytics.com/hub/quickstart",
    "https://docs.ultralytics.com/hub/sdk",
    "https://docs.ultralytics.com/hub/teams",
    "https://dragon.nuance.com/en-us/dragon-medical-one",
    "https://en.wikipedia.org/wiki/Covariate_shift",
    "https://en.wikipedia.org/wiki/Encoder-decoder",
    "https://en.wikipedia.org/wiki/Label_noise",
    "https://en.wikipedia.org/wiki/Multi-object_tracking",
    "https://en.wikipedia.org/wiki/Occlusion_(computer_graphics)",
    "https://en.wikipedia.org/wiki/Occlusion_(computer_vision)",
    "https://en.wikipedia.org/wiki/Perception_(artificial_intelligence)",
    "https://en.wikipedia.org/wiki/Reversible_neural_network",
    "https://ercole.roma3.infn.it/wp-content/uploads/2024/04/Manuscript_IMEKO_send65-1.pdf",
    "https://github.com/dependabot]",
    "https://github.com/maycuatroi",
    "https://github.com/mlfoundations/openclip",
    "https://github.com/ultralytics/ultralytics/blob/main/docs/en/hub/inference-api.md",
    "https://github.com/ultralytics/ultralytics/main/examples",
    "https://hub.ultralytics.com",
    "https://iapp.org/resources/article/pseudonymization-101/",
    "https://labs.openai.com/",
    "https://machinelearningmastery.com/sparse-representations-for-deep-learning/",
    "https://monkeylearn.com/keyword-extraction/",
    "https://monkeylearn.com/text-classification/",
    "https://nascoict.org/about-us/",
    "https://nascoict.org/en/",
    "https://nascoict.org/nascotech-en/",
    "https://neptune.ai/blog/understanding-gradient-clipping-and-how-to-implement-it",
    "https://neptune.ai/blog/understanding-gradient-clipping-and-how-to-use-it",
    "https://oag.ca.gov/privacy/ccpa",
    "https://openai.com/index/gpt-3/",
    "https://openai.com/index/grokking/",
    "https://openai.com/research/alignment",
    "https://openai.com/research/proximal-policy-optimization",
    "https://openai.com/research/proximal-policy-optimization-algorithms",
    "https://openai.com/safety/research",
    "https://paperswithcode.com/method/silu",
    "https://pypi.jetson-ai-lab.dev/jp/cu126",
    "https://pypi.jetson-ai-lab.dev/jp6/cu126",
    "https://research.ibm.com/blog/ai-fairness-360",
    "https://research.ibm.com/blog/what-is-alignment-ai",
    "https://statisticsbyjim.com/hypothesis-testing/type-ii-error/",
    "https://statisticsbyjim.com/regression/ols-linear-regression-model/",
    "https://towardsdatascience.com/uncertainty-sampling-cheatsheet-ec57bc067c0b",
    "https://vtechworks.lib.vt.edu/items/2bc637cb-916e-4d74-bd8d-4f6cd1f7ce29",
    "https://www.accountablehq.com/post/ai-and-hipaa",
    "https://www.aclweb.org/portal/",
    "https://www.acm.org/articles/pubs-newsletter/2021/blue-diamond-algorithmic-fairness",
    "https://www.autodesk.com/toronto/generative-design",
    "https://www.cricbuzz.com/cricket-full-commentary/a114987/gt-vs-pbks-5th-match-indian-premier-league-2025",
    "https://www.cricbuzz.com/cricket-full-commentary/a114987/gt-vs-pbks-5th-match-indian-premier-league-2025#:~:text=18.5-,Vijaykumar%20Vyshak%20to%20Rahul%20Tewatia,-%2C%20no%20run%2C%20now",
    "https://www.cricjp.com/cricket-no-ball-rules-know-24-widely-known-rules/",
    "https://www.datacamp.com/tutorial/svm-classifier-scikit-learn",
    "https://www.deepwizai.com/projects/an-unsupervised-neural-image-compression-algorithm",
    "https://www.edmundoptics.com/knowledge-center/application-notes/imaging/illumination-fundamentals/",
    "https://www.edoeb.admin.ch/edoeb/en/home/the-fdpic/contact.html",
    "https://www.fincen.gov/news/news-releases/fincen-alerts-financial-institutions-potential-us-commercial-real-estate",
    "https://www.gsi.go.jp/ENGLISH/",
    "https://www.hsls.pitt.edu/obrc/index.php?page=URL1053633750",
    "https://www.icao.int/nacc/documents/meetings/2014/sspsmsant/annex19.pdf",
    "https://www.ieee.org/about/news/2016/smart-cities.html",
    "https://www.ieee.org/about/technologies/consumer-electronics.html",
    "https://www.ieee.org/technical-activities/pubs/fog-computing",
    "https://www.ieee.org/technical-activities/pubs/fog-computing.html",
    "https://www.mastercard.com/news/perspectives/2023/how-ai-is-fighting-fraud/",
    "https://www.mathworks.com/discovery/fuzzy-logic.html",
    "https://www.mathworks.com/discovery/sensor-fusion.html",
    "https://www.nifa.usda.gov/about-nifa/blogs/researchers-helping-protect-crops-pests",
    "https://www.sciencedirect.com/science/article/pii/S095219762100122X",
    "https://www.sciencedirect.com/science/article/pii/S221083271200026X",
    "https://www.sciencedirect.com/science/article/pii/S221083271500030X",
    "https://www.sciencedirect.com/topics/computer-science/computational-efficiency",
    "https://www.sciencedirect.com/topics/computer-science/equalized-odds",
    "https://www.sciencedirect.com/topics/computer-science/facial-landmark",
    "https://www.sciencedirect.com/topics/computer-science/financial-fraud-detection",
    "https://www.sciencedirect.com/topics/computer-science/fitness-function",
    "https://www.sciencedirect.com/topics/computer-science/genetic-diversity",
    "https://www.sciencedirect.com/topics/computer-science/occlusion-handling",
    "https://www.sciencedirect.com/topics/computer-science/perception-system",
    "https://www.sciencedirect.com/topics/computer-science/spatial-awareness",
    "https://www.sciencedirect.com/topics/engineering/automated-visual-inspection",
    "https://www.sciencedirect.com/topics/engineering/autonomous-systems",
    "https://www.sciencedirect.com/topics/engineering/kinematics",
    "https://www.sciencedirect.com/topics/engineering/perception-system",
    "https://www.scribbr.com/statistics/regression-analysis/",
    "https://www.sowit.fr/",
    "https://www.spatialpost.com/difference-between-lidar-and-camera/",
    "https://www.sportstravelmagazine.com/wp-content/uploads/2019/08/cropped-Webp.net-resizeimage.png",
    "https://www.tableau.com/learn/articles/data-analytics",
    "https://www.techno-science.net/en/news/these-kamikaze-drones-equipped-with-ai-are-reinventing-military-tactics-N25946.html",
    "https://www.techopedia.com/the-6-most-amazing-ai-advances-in-agriculture/2/33177",
    "https://www.transportation.gov/research-and-technology/connected-vehicles",
    "https://www.travelport.com/press-release/travelport-launches-global-accelerator",
    "https://www.turing.ac.uk/research/research-projects/ai-financial-services",
    "https://www.ultralytics.com/hub",
    "https://www.usda.gov/topics/farming/precision-agriculture",
    "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-aerial-photography-aerial-photography-single-frames",
    "https://www.usgs.gov/faqs/what-are-difference-between-satellite-imagery-and-aerial-photography",
    "https://zhuanlan.zhihu.com/p/605141797",
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
    "ftc.gov",  # answers non-browser clients with 404 even for live pages
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
        "/dev/",  # unstable development docs
        ".appspot.com",  # app-hosting origins behind a vanity domain
        ".herokuapp.com",
        ".azurewebsites.net",
        ".cloudfront.net",
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
        "signin",
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
REDIRECT_END_REJECT_PATTERNS = (  # (destination pattern, reject only when the start URL does not match it too)
    (re.compile(r"(?i)[?&](?:Expires|Signature|X-Amz-Signature|token)="), False),  # signed CDN URL
    (re.compile(r"(?i)[?&](?:session_sync_attempted|redirect_url|continue|state|code)="), True),  # auth handshake
    (re.compile(r"(?i)^[^?#]*/(?:en|[a-z]{2}-[a-z]{2,4})/|[?&](?:gl|hl|lang|locale)="), True),  # locale or geo variant
    (re.compile(r"(?i)[?&](?:utm_\w+|ref|source)="), True),  # tracking params
    (re.compile(r"^https?://[^/?#]+/[^/?#]*(?:/[^/?#]*)*?/([^/?#]+)/\1(?=[/?#]|$)"), True),  # duplicated segment
    (re.compile(r"^https?://[^/?#]*/?(?:[?#]|$)"), True),  # deep link collapsing to a homepage
)
URL_REWRITES = {  # permanent moves to apply before checking
    "https://docs.ultralytics.com/glossary/": "https://www.ultralytics.com/glossary/",
}
URL_PATTERN = re.compile(
    r"\[(?P<md_text>[^]]+)]\((?P<md_url>[^)]+)\)"  # Matches Markdown links [text](url)
    r"|"
    r"(?P<plain_url>"  # Start capturing group for plaintext URLs
    r"(?:https?://)?"  # Optional http:// or https://
    r"(?:www\.)?"  # Optional www.
    r"(?:[\w.-]+)?"  # Optional domain name and subdomains
    r"\.[a-zA-Z]{2,}"  # TLD
    r"(?:/[^\s\"')\]<>]*)?"  # Optional path
    r")"
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
    url = str(url).strip('"').strip("'").rstrip(".,:;!?`\\").replace(".git@main", "").replace("git+", "")
    # Second pass for nested quotes/punctuation
    url = url.strip('"').strip("'").rstrip(".,:;!?`\\")
    return url


def allow_redirect(start="", end=""):
    """Check if a redirect target should be applied based on simple allow rules."""
    start_lower = start.lower()
    end_lower = end.lower()
    return (
        end
        and end.startswith("https://")
        and end.rstrip("/") != start.rstrip("/")  # a trailing slash alone is not worth rewriting
        and not start_lower.endswith(".git")  # git clone URLs, i.e. https://github.com/org/repo.git
        and all(item not in end_lower for item in REDIRECT_END_IGNORE_LIST)
        and all(item not in start_lower for item in REDIRECT_START_IGNORE_LIST)
        and not any(
            pattern.search(end) and not (added and pattern.search(start))
            for pattern, added in REDIRECT_END_REJECT_PATTERNS
        )
    )


def is_homepage(url):
    """Return True when a URL points at a site root."""
    return not parse.urlsplit(url).path.strip("/")


def same_site(url1, url2):
    """Return True when two URLs share a host, ignoring a leading www."""
    hosts = [(parse.urlsplit(u).hostname or "").lower() for u in (url1, url2)]
    return len({h[4:] if h.startswith("www.") else h for h in hosts}) == 1


def normalize_redirect_url(url):
    """Drop the trailing slash that Ultralytics hosts add to redirect destinations, keeping any query or fragment."""
    parts = parse.urlsplit(url)
    hostname = parts.hostname or ""
    if hostname == "ultralytics.com" or hostname.endswith(".ultralytics.com"):
        parts = parts._replace(path=parts.path.rstrip("/"))
    return parse.urlunsplit(parts)


def brave_search(query, api_key, count=5):
    """Search for alternative URLs using Brave Search API."""
    if not api_key:
        return
    if len(query) > 400:
        print(f"WARNING ⚠️ Brave search query length {len(query)} exceed limit of 400 characters, truncating.")
    url = f"https://api.search.brave.com/res/v1/web/search?q={parse.quote(query.strip()[:400])}&count={count}"
    try:
        response = requests.get(
            url, headers={"X-Subscription-Token": api_key, "Accept": "application/json"}, timeout=10
        )
        data = response.json() if response.status_code == 200 else {}
    except Exception as e:  # a search outage must never block the caller from returning its text
        print(f"WARNING ⚠️ Brave search failed: {e}")
        return []
    results = data.get("web", {}).get("results", []) if data else []
    return [result.get("url") for result in results if result.get("url")]


def is_url(url, session=None, check=True, max_attempts=3, timeout=3, return_url=False, redirect=False):
    """Check if string is URL and optionally verify it exists, with fallback for GitHub repos.

    Returns True for a live URL, False for a dead one, and None when the check is inconclusive (timeouts, connection or
    server errors), so callers can report it without treating it as dead.
    """
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

            start = url
            for attempt in range(max_attempts):
                for method in ("head", "get"):  # GET also covers servers that refuse, reset or hang on HEAD
                    try:
                        response = getattr(requester, method)(url, stream=method == "get", **kwargs)
                    except Exception:
                        continue
                    response.close()
                    if response.history and is_homepage(response.url) and not is_homepage(start):
                        return (False, response.url) if return_url else False  # a soft 404 to the homepage
                    # Only update URL if there were actual HTTP redirects (indicated by response.history)
                    if redirect and response.history and allow_redirect(start=url, end=response.url):
                        url = normalize_redirect_url(response.url)
                    if response.status_code not in BAD_HTTP_CODES:
                        return (True, url) if return_url else True
                    if method == "get":  # GET answered with a bad status, which is final
                        # If GitHub and check fails (repo might be private), add the base GitHub URL to ignore list
                        if result.hostname == "github.com":
                            parts = result.path.strip("/").split("/")
                            if len(parts) >= 2:
                                base_url = f"https://github.com/{parts[0]}/{parts[1]}"  # https://github.com/org/repo
                                if requester.head(base_url, **kwargs).status_code == 404:
                                    URL_IGNORE_LIST.add(base_url)
                                    return (True, url) if return_url else True
                        valid = False if response.status_code in DEAD_HTTP_CODES else None
                        return (valid, url) if return_url else valid
                if attempt < max_attempts - 1:
                    time.sleep(2**attempt)  # both requests raised, so retry with exponential backoff
            return (None, url) if return_url else None
        return (True, url) if return_url else True
    except Exception:
        return (False, url) if return_url else False


def check_links_in_string(text, verbose=True, return_bad=False, replace=False):
    """Check URLs outside code, optionally applying redirects, search fixes and unlinking of unfixable Markdown links."""
    # Code URLs are often partial (f-strings, base URLs), so fenced and inline code is never checked or rewritten
    parts = re.split(r"(```.*?```|`[^`\n]+`)", text, flags=re.DOTALL)
    if replace:
        for i in range(0, len(parts), 2):
            for old, new in URL_REWRITES.items():
                parts[i] = parts[i].replace(old, new)
    urls = []
    for match in (m for part in parts[::2] for m in URL_PATTERN.finditer(part)):
        url = match["md_url"] or match["plain_url"]
        if url and parse.urlparse(url).scheme:
            urls.append((match["md_text"] or "", clean_url(url)))

    with requests.Session() as session, ThreadPoolExecutor(max_workers=64) as executor:
        session.headers.update(REQUESTS_HEADERS)
        session.cookies = requests.cookies.RequestsCookieJar()
        unique = list(dict.fromkeys(url for _, url in urls))  # check each URL once
        checked = dict(zip(unique, executor.map(lambda u: is_url(u, session, return_url=True, redirect=True), unique)))
        results = [checked[url] for _, url in urls]
        bad_urls = [url for (title, url), (valid, redirect) in zip(urls, results) if not valid]

        if replace:
            replacements, searched = {}, set()

            # Process all URLs for replacements
            brave_api_key = os.getenv("BRAVE_API_KEY")
            for (title, url), (valid, redirect) in zip(urls, results):
                # Handle dead URLs with Brave search; an inconclusive check (None) keeps its link. Two queries, not two
                # attempts: the dead URL biases the first toward the site root, so the second drops it and searches the
                # link text on its domain.
                if valid is False:
                    if url in searched:  # search once per URL, however many times it occurs
                        continue
                    searched.add(url)
                    for query in (
                        f"{(redirect or url)[:200]} {title[:199]}",
                        f"{title[:199]} {parse.urlparse(url).netloc}",
                    ):
                        search_urls = brave_search(query, brave_api_key, count=3) or []
                        candidates = (  # a page that moved within its site, never another site's page
                            u
                            for u in search_urls
                            if u != url and same_site(url, u) and allow_redirect(start=url, end=u)
                        )
                        if best_url := next((u for u in candidates if is_url(u, session)), None):
                            replacements[url] = best_url
                            break
                # Handle redirects for valid URLs
                elif valid and redirect and redirect != url:
                    replacements[url] = redirect

            if verbose and replacements:
                print(
                    f"WARNING ⚠️ replaced {len(replacements)} links:\n"
                    + "\n".join(f"  {k}: {v}" for k, v in replacements.items())
                )
            dead = {url for (_, url), (valid, _) in zip(urls, results) if valid is False} - set(replacements)

            def replace_link(match):
                """Swap a matched URL for its replacement, or unlink a dead Markdown link that nothing could fix."""
                group = "md_url" if match["md_url"] else "plain_url"
                raw_url = match[group]
                if not (new_url := replacements.get(clean_url(raw_url))):
                    return match["md_text"] if group == "md_url" and clean_url(raw_url) in dead else match[0]
                start, end = (i - match.start() for i in match.span(group))
                suffix = raw_url[len(raw_url.rstrip(".,:;!?`\\")) :]  # trailing punctuation clean_url() dropped
                return f"{match[0][:start]}{new_url}{suffix}{match[0][end:]}"

            text = "".join(part if i % 2 else URL_PATTERN.sub(replace_link, part) for i, part in enumerate(parts))
            bad_urls = [url for url in bad_urls if url not in replacements]  # unfixable links stay reported

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
