# Ultralytics Actions 🚀, AGPL-3.0 license https://ultralytics.com/license

import hashlib
import re
import shutil
import subprocess
from pathlib import Path


def extract_code_blocks(markdown_content):
    """Extracts Python code blocks from markdown content using regex pattern matching."""
    pattern = r"^( *)```(?:python|py|\{[ ]*\.py[ ]*\.annotate[ ]*\})\n(.*?)\n\1```"
    code_block_pattern = re.compile(pattern, re.DOTALL | re.MULTILINE)
    return code_block_pattern.findall(markdown_content)


def remove_indentation(code_block, num_spaces):
    """Removes specified leading spaces from each line in a code block to adjust indentation."""
    lines = code_block.split("\n")
    stripped_lines = [line[num_spaces:] if len(line) >= num_spaces else line for line in lines]
    return "\n".join(stripped_lines)


def add_indentation(code_block, num_spaces):
    """Adds specified number of leading spaces to non-empty lines in a code block."""
    indent = " " * num_spaces
    lines = code_block.split("\n")
    indented_lines = [indent + line if line.strip() != "" else line for line in lines]
    return "\n".join(indented_lines)


def format_code_with_ruff(temp_dir):
    """Formats Python code files in the specified directory using ruff linter and docformatter tools."""
    try:
        # Run ruff format
        subprocess.run(
            [
                "ruff",
                "format",
                "--line-length=120",
                str(temp_dir),
            ],
            check=True,
        )
        print("Completed ruff format ✅")
    except Exception as e:
        print(f"ERROR running ruff format ❌ {e}")

    try:
        # Run ruff check with ignored rules:
        # F821: Undefined name
        # F841: Local variable is assigned to but never used
        subprocess.run(
            [
                "ruff",
                "check",
                "--fix",
                "--extend-select=I",
                "--ignore=F821,F841",
                str(temp_dir),
            ],
            check=True,
        )
        print("Completed ruff check ✅")
    except Exception as e:
        print(f"ERROR running ruff check ❌ {e}")

    try:
        # Run docformatter
        subprocess.run(
            [
                "docformatter",
                "--wrap-summaries=120",
                "--wrap-descriptions=120",
                "--pre-summary-newline",
                "--close-quotes-on-newline",
                "--in-place",
                "--recursive",
                str(temp_dir),
            ],
            check=True,
        )
        print("Completed docformatter ✅")
    except Exception as e:
        print(f"ERROR running docformatter ❌ {e}")


def generate_temp_filename(file_path, index):
    """Generates a unique temporary filename using a hash of the file path and index."""
    unique_string = f"{file_path.parent}_{file_path.stem}_{index}"
    unique_hash = hashlib.md5(unique_string.encode()).hexdigest()
    return f"temp_{unique_hash}.py"


def process_markdown_file(file_path, temp_dir, verbose=False):
    """Processes a markdown file, extracting Python code blocks for formatting and updating the original file."""
    try:
        markdown_content = Path(file_path).read_text()
        code_blocks = extract_code_blocks(markdown_content)
        temp_files = []

        for i, (num_spaces, code_block) in enumerate(code_blocks):
            if verbose:
                print(f"Extracting code block {i} from {file_path}")
            num_spaces = len(num_spaces)
            code_without_indentation = remove_indentation(code_block, num_spaces)

            # Generate a unique temp file path
            temp_file_path = temp_dir / generate_temp_filename(file_path, i)
            with open(temp_file_path, "w") as temp_file:
                temp_file.write(code_without_indentation)
            temp_files.append((num_spaces, code_block, temp_file_path))

        return markdown_content, temp_files

    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None, None


def update_markdown_file(file_path, markdown_content, temp_files):
    """Updates a markdown file with formatted Python code blocks extracted and processed externally."""
    for num_spaces, original_code_block, temp_file_path in temp_files:
        try:
            with open(temp_file_path) as temp_file:
                formatted_code = temp_file.read().rstrip("\n")  # Strip trailing newlines
            formatted_code_with_indentation = add_indentation(formatted_code, num_spaces)

            # Replace both `python` and `py` code blocks
            for lang in ["python", "py", "{ .py .annotate }"]:
                markdown_content = markdown_content.replace(
                    f"{' ' * num_spaces}```{lang}\n{original_code_block}\n{' ' * num_spaces}```",
                    f"{' ' * num_spaces}```{lang}\n{formatted_code_with_indentation}\n{' ' * num_spaces}```",
                )
        except Exception as e:
            print(f"Error updating code block in file {file_path}: {e}")

    try:
        with open(file_path, "w") as file:
            file.write(markdown_content)
    except Exception as e:
        print(f"Error writing file {file_path}: {e}")


def main(root_dir=Path.cwd(), verbose=False):
    """Processes markdown files, extracts and formats Python code blocks, and updates the original files."""
    root_path = Path(root_dir)
    markdown_files = list(root_path.rglob("*.md"))
    temp_dir = Path("temp_code_blocks")
    temp_dir.mkdir(exist_ok=True)

    # Extract code blocks and save to temp files
    all_temp_files = []
    for markdown_file in markdown_files:
        if verbose:
            print(f"Processing {markdown_file}")
        markdown_content, temp_files = process_markdown_file(markdown_file, temp_dir)
        if markdown_content and temp_files:
            all_temp_files.append((markdown_file, markdown_content, temp_files))

    # Format all code blocks with ruff
    format_code_with_ruff(temp_dir)

    # Update markdown files with formatted code blocks
    for markdown_file, markdown_content, temp_files in all_temp_files:
        update_markdown_file(markdown_file, markdown_content, temp_files)

    # Clean up temp directory
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
