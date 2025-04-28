# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import hashlib
import re
import shutil
import subprocess
from pathlib import Path


def extract_code_blocks(markdown_content):
    """Extracts Python and Bash code blocks from markdown content using regex pattern matching."""
    # Python code blocks
    py_pattern = r"^( *)```(?:python|py|\{[ ]*\.py[ ]*\.annotate[ ]*\})\n(.*?)\n\1```"
    py_code_blocks = re.compile(py_pattern, re.DOTALL | re.MULTILINE).findall(markdown_content)

    # Bash code blocks
    bash_pattern = r"^( *)```(?:bash|sh|shell)\n(.*?)\n\1```"
    bash_code_blocks = re.compile(bash_pattern, re.DOTALL | re.MULTILINE).findall(markdown_content)

    return {"python": py_code_blocks, "bash": bash_code_blocks}


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
        # D101 Missing docstring in public class
        # D103 Missing docstring in public function
        # F821 Undefined name
        # F841 Local variable is assigned to but never used
        subprocess.run(
            [
                "ruff",
                "check",
                "--fix",
                "--unsafe-fixes",
                "--extend-select=I,D,UP",
                "--target-version=py38",
                "--ignore=D100,D101,D103,D104,D203,D205,D212,D213,D401,D406,D407,D413,F821,F841",
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


def format_bash_with_prettier(temp_dir):
    """Formats bash script files in the specified directory using prettier."""
    try:
        # Run prettier with explicit config path
        result = subprocess.run(
            "npx prettier --write --plugin=$(npm root -g)/prettier-plugin-sh/lib/index.cjs ./**/*.sh",
            shell=True,  # must use shell=True to expand internal $(cmd)
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"ERROR running prettier-plugin-sh ❌ {result.stderr}")
        else:
            print("Completed bash formatting ✅")
    except Exception as e:
        print(f"ERROR running prettier-plugin-sh ❌ {e}")


def generate_temp_filename(file_path, index, code_type):
    """Creates unique temp filename with full path info for debugging."""
    stem = file_path.stem
    code_letter = code_type[0]  # 'p' for python, 'b' for bash
    path_part = str(file_path.parent).replace("/", "_").replace("\\", "_").replace(" ", "-")
    hash_val = hashlib.md5(f"{file_path}_{index}".encode()).hexdigest()[:6]
    ext = ".py" if code_type == "python" else ".sh"
    filename = f"{stem}_{path_part}_{code_letter}{index}_{hash_val}{ext}"
    return re.sub(r"[^\w\-.]", "_", filename)


def process_markdown_file(file_path, temp_dir, process_python=True, process_bash=True, verbose=False):
    """Processes a markdown file, extracting code blocks for formatting and updating the original file."""
    try:
        markdown_content = Path(file_path).read_text()
        code_blocks_by_type = extract_code_blocks(markdown_content)
        temp_files = []

        # Process all code block types based on flags
        code_types = []
        if process_python:
            code_types.append(("python", 0))
        if process_bash:
            code_types.append(("bash", 1000))

        for code_type, offset in code_types:
            for i, (num_spaces, code_block) in enumerate(code_blocks_by_type[code_type]):
                if verbose:
                    print(f"Extracting {code_type} code block {i} from {file_path}")

                num_spaces = len(num_spaces)
                code_without_indentation = remove_indentation(code_block, num_spaces)
                temp_file_path = temp_dir / generate_temp_filename(file_path, i + offset, code_type)

                with open(temp_file_path, "w") as temp_file:
                    temp_file.write(code_without_indentation)

                temp_files.append((num_spaces, code_block, temp_file_path, code_type))

        return markdown_content, temp_files

    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None, None


def update_markdown_file(file_path, markdown_content, temp_files):
    """Updates a markdown file with formatted code blocks."""
    for num_spaces, original_code_block, temp_file_path, code_type in temp_files:
        try:
            with open(temp_file_path) as temp_file:
                formatted_code = temp_file.read().rstrip("\n")  # Strip trailing newlines
            formatted_code_with_indentation = add_indentation(formatted_code, num_spaces)

            # Define the language tags for each code type
            lang_tags = {"python": ["python", "py", "{ .py .annotate }"], "bash": ["bash", "sh", "shell"]}

            # Replace the code blocks with the formatted version
            for lang in lang_tags[code_type]:
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


def main(root_dir=Path.cwd(), process_python=True, process_bash=True, verbose=False):
    """Processes markdown files, extracts and formats code blocks, and updates the original files."""
    root_path = Path(root_dir)
    markdown_files = list(root_path.rglob("*.md"))
    temp_dir = Path("temp_code_blocks")
    temp_dir.mkdir(exist_ok=True)

    # Extract code blocks and save to temp files
    all_temp_files = []
    for markdown_file in markdown_files:
        if verbose:
            print(f"Processing {markdown_file}")
        markdown_content, temp_files = process_markdown_file(
            markdown_file, temp_dir, process_python, process_bash, verbose
        )
        if markdown_content and temp_files:
            all_temp_files.append((markdown_file, markdown_content, temp_files))

    # Format code blocks based on flags
    if process_python:
        format_code_with_ruff(temp_dir)  # Format Python files
    if process_bash:
        format_bash_with_prettier(temp_dir)  # Format Bash files

    # Update markdown files with formatted code blocks
    for markdown_file, markdown_content, temp_files in all_temp_files:
        update_markdown_file(markdown_file, markdown_content, temp_files)

    # Clean up temp directory
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main(process_python=True, process_bash=True)
