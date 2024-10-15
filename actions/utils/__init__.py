from .github_utils import (
    GITHUB_TOKEN,
    GITHUB_API_URL,
    GITHUB_HEADERS,
    get_pr_diff,
    get_github_data,
    graphql_request,
)
from .openai_utils import OPENAI_MODEL, OPENAI_API_KEY, get_completion
from .common_utils import remove_html_comments
