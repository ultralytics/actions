import re

def remove_html_comments(body: str) -> str:
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()

