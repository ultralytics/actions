# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import re


def remove_html_comments(body: str) -> str:
    """Removes HTML comments from a string using regex pattern matching."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
