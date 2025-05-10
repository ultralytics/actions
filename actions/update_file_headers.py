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
IGNORE_PATHS = [
    ".idea",
    ".venv",
    "env",
    "node_modules",
    ".git",
    "__pycache__",
    "mkdocs_github_authors.yaml",
    # Build and distribution directories
    "dist",
    "build",
    ".eggs",
    "site",  # mkdocs build directory
    # Generated code
    "generated",
    "auto_gen",
    # Lock files
    "lock",
    # Minified files
    ".min.js",
    ".min.css",
]


def update_file(file_path, prefix, block_start, block_end, base_header):
    """Update file with the correct header and proper spacing."""
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
    elif block_start and block_end:
        formatted_header = f"{block_start}{base_header}{block_end}\n"
    else:
        formatted_header = f"# {base_header}\n"

    # Keep shebang line if it exists
    start_idx = 0
    if lines and lines[0].startswith("#!"):
        start_idx = 1

    modified = False
    new_lines = lines[:start_idx]
    remaining_lines = lines[start_idx:]

    # If first line is already the exact header we want
    if remaining_lines and remaining_lines[0] == formatted_header:
        # Check if spacing is correct
        new_lines.append(remaining_lines[0])
        if len(remaining_lines) > 1:
            second_line = remaining_lines[1].strip()
            if second_line == "" or second_line in ["#", "//", "/*", "*", "<!--", "%"]:
                # Spacing is correct, append the rest
                new_lines.extend(remaining_lines[1:])
            else:
                # Add blank line
                new_lines.append("\n")
                new_lines.extend(remaining_lines[1:])
                modified = True
        else:
            # Only header exists, no need for blank line
            pass
    # Check if first line has AGPL but is not the exact header
    elif remaining_lines and "AGPL" in remaining_lines[0] and remaining_lines[0] != formatted_header:
        # Replace with proper header
        new_lines.append(formatted_header)
        modified = True

        # Check if second line is blank or commented
        if len(remaining_lines) > 1:
            second_line = remaining_lines[1].strip()
            if second_line == "" or second_line in ["#", "//", "/*", "*", "<!--", "%"]:
                # Keep existing blank/comment line
                new_lines.append(remaining_lines[1])
                new_lines.extend(remaining_lines[2:])
            else:
                # Add blank line
                new_lines.append("\n")
                new_lines.extend(remaining_lines[1:])
        else:
            # Only header line, no need for blank line after
            pass
    # No header found, add it
    else:
        # Add header at the beginning
        new_lines.append(formatted_header)
        # Add blank line if content follows
        if remaining_lines and remaining_lines[0].strip():
            new_lines.append("\n")
        new_lines.extend(remaining_lines)
        modified = True

    if modified:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False

    return False


def main(*args, **kwargs):
    """Automates file header updates for all files in the specified directory."""
    event = Action(*args, **kwargs)

    if "ultralytics" in event.repository.lower():
        if event.is_repo_private() and event.repository.startswith("ultralytics/"):
            from datetime import datetime

            notice = f"Copyright © 2014-{datetime.now().year}"
            header = f"Ultralytics Inc. 🚀 {notice} - CONFIDENTIAL - https://ultralytics.com - All Rights Reserved"
        else:
            header = "Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license"
    elif HEADER and HEADER.lower() not in {"true", "false", "none"}:
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
