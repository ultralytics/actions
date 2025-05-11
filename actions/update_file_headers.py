# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import os
from pathlib import Path

from actions.utils import Action

# Base header text
HEADER = os.getenv("HEADER")

# Map file extensions to comment styles
COMMENT_MAP = {
    # Python style
    ".py": ("# ", None, None),
    ".yml": ("# ", None, None),
    ".yaml": ("# ", None, None),
    ".toml": ("# ", None, None),
    ".sh": ("# ", None, None),  # Bash scripts
    ".bash": ("# ", None, None),  # Bash scripts
    # C/C++/Java/JS style
    ".c": ("// ", "/* ", " */"),  # C files
    ".cpp": ("// ", "/* ", " */"),  # C++ files
    ".h": ("// ", "/* ", " */"),  # C/C++ header files
    ".hpp": ("// ", "/* ", " */"),  # C++ header files
    ".swift": ("// ", "/* ", " */"),
    ".js": ("// ", "/* ", " */"),
    ".ts": ("// ", "/* ", " */"),  # TypeScript files
    ".dart": ("// ", "/* ", " */"),  # Dart/Flutter files
    ".rs": ("// ", "/* ", " */"),  # Rust files
    ".java": ("// ", "/* ", " */"),  # Android Java
    ".kt": ("// ", "/* ", " */"),  # Android Kotlin
    # CSS style
    ".css": (None, "/* ", " */"),
    # HTML/XML style
    ".html": (None, "<!-- ", " -->"),
    ".xml": (None, "<!-- ", " -->"),  # Android XML
    # MATLAB style
    ".m": ("% ", None, None),
}

# Ignore these Paths (do not update their headers)
IGNORE_PATHS = {
    ".idea",
    ".venv",
    "env/",
    "node_modules",
    ".git",
    "__pycache__",
    "mkdocs_github_authors.yaml",
    # Build and distribution directories
    "dist/",
    "build/",
    ".eggs",
    "site/",  # mkdocs build directory
    # Generated code
    "generated/",
    "auto_gen/",
    # Lock files
    "lock",
    # Minified files
    ".min.js",
    ".min.css",
}


def update_file(file_path, prefix, block_start, block_end, base_header):
    """Update file preserving comments after header or adding blank line."""
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    if not lines:
        return False

    # Format the header based on comment style
    if prefix:
        formatted_header = f"{prefix}{base_header}\n"
        comment_marker = prefix
    elif block_start and block_end:
        formatted_header = f"{block_start}{base_header}{block_end}\n"
        comment_marker = block_start.strip()
    else:
        formatted_header = f"# {base_header}\n"
        comment_marker = "# "

    # Save original content for comparison
    original_content = "".join(lines)
    prefix_lines = []

    # Check for special first line
    special_line_index = -1
    if lines and (lines[0].startswith("#!") or lines[0].startswith("<?xml") or lines[0].startswith("<!DOCTYPE")):
        special_line_index = 0
        prefix_lines.append(lines[0])

    # Find existing header
    header_index = -1
    start_idx = special_line_index + 1 if special_line_index >= 0 else 0
    end_idx = min(start_idx + 5, len(lines))  # Look in first few lines

    for i in range(start_idx, end_idx):
        if "Ultralytics " in lines[i]:
            header_index = i
            break

    # Add the formatted header to prefix lines
    prefix_lines.append(formatted_header)

    # Determine where content starts and check for comment line after header
    content_lines = []
    has_comment_after_header = False
    
    if header_index >= 0:
        next_line_idx = header_index + 1
        
        # Check if there's a line after the header and if it's a comment or empty
        if next_line_idx < len(lines):
            next_line = lines[next_line_idx].strip()
            if next_line == "":
                # Empty line - we'll add our own later
                content_start = next_line_idx + 1
            elif next_line.startswith(comment_marker):
                # Comment line - preserve it
                prefix_lines.append(lines[next_line_idx])
                has_comment_after_header = True
                content_start = next_line_idx + 1
            else:
                # Regular code - no blank line or comment after header
                content_start = next_line_idx
        else:
            content_start = next_line_idx
            
        content_lines = lines[content_start:]
    else:
        # No header found
        if special_line_index >= 0:
            content_lines = lines[special_line_index + 1:]
        else:
            content_lines = lines

    # Add blank line before content if no comment line was found and first content line isn't already blank
    if not has_comment_after_header and content_lines and content_lines[0].strip():
        prefix_lines.append("\n")

    # Combine prefix lines and content lines
    final_lines = prefix_lines + content_lines

    # Check if content changed
    new_content = "".join(final_lines)
    if new_content == original_content:
        return False

    # Write updated content
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(final_lines)
        return True
    except Exception as e:
        print(f"Error writing {file_path}: {e}")
        return False


def main(*args, **kwargs):
    """Automates file header updates for all files in the specified directory."""
    event = Action(*args, **kwargs)

    if "ultralytics" in event.repository.lower():
        if event.is_repo_private() and event.repository.startswith("ultralytics/"):
            from datetime import datetime

            notice = f"© 2014-{datetime.now().year} Ultralytics Inc. 🚀"
            header = f"{notice} All rights reserved. CONFIDENTIAL: Unauthorized use or distribution prohibited."
        else:
            header = "Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license"
    elif HEADER and str(HEADER).lower() not in {"true", "false", "none"}:
        header = HEADER
    else:
        return

    directory = Path.cwd()
    total = changed = unchanged = 0
    for ext, comment_style in COMMENT_MAP.items():
        prefix, block_start, block_end = comment_style

        for file_path in directory.rglob(f"*{ext}"):
            if any(part in str(file_path) for part in IGNORE_PATHS):
                continue

            total += 1
            if update_file(file_path, prefix, block_start, block_end, header):
                print(f"Updated: {file_path.relative_to(directory)}")
                changed += 1
            else:
                unchanged += 1

    print(f"Headers: {total}, Updated: {changed}, Unchanged: {unchanged}")


if __name__ == "__main__":
    main()
