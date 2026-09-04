# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

TABLE_ROW = re.compile(r"^( {4,})\|(.*)$")
DIVIDER = re.compile(r"^:?-+:?$")
FENCE = re.compile(r"^( *)(`{3,}|~{3,})")
FENCE_CLOSE = re.compile(r"^( *)(`{3,}|~{3,})[ \t]*$")
CONTAINER = re.compile(r"^(?:(?:!!!|\?\?\?\+?)\s+\S|===[+!]?\s+([\"']).+\1\s*$)")


def _width(text: str) -> int:
    """Return terminal width, collapsing common emoji sequences to two columns."""
    width = last = 0
    join = skip = False
    for i, char in enumerate(text):
        code = ord(char)
        if skip:
            skip = False
            continue
        if char == "\u200d":
            join = True
            continue
        if code in (0xFE0F, 0x20E3) or 0x1F3FB <= code <= 0x1F3FF:
            if last == 1:
                width += 1
                last = 2
            continue
        if unicodedata.combining(char):
            continue
        if join:
            join = False
            continue
        if 0x1F1E6 <= code <= 0x1F1FF and i + 1 < len(text) and 0x1F1E6 <= ord(text[i + 1]) <= 0x1F1FF:
            width, last, skip = width + 2, 2, True
        else:
            last = 2 if unicodedata.east_asian_width(char) in "WF" else 1
            width += last
    return width


def _align_table(lines: list[str]) -> list[str]:
    """Align a possible pipe table, or return it unchanged when malformed."""
    indent = TABLE_ROW.match(lines[0]).group(1)
    rows = []
    for line in lines:
        cells = re.split(r"(?<!\\)\|", TABLE_ROW.match(line).group(2))
        if cells[-1].strip() == "":
            cells.pop()
        rows.append([cell.strip() for cell in cells])
    if (
        len(rows) < 3
        or not all(DIVIDER.fullmatch(cell) for cell in rows[1])
        or any(len(row) != len(rows[0]) for row in rows)
    ):
        return lines

    aligns = [(cell.startswith(":"), cell.endswith(":")) for cell in rows[1]]
    widths = [max(3, *(_width(row[i]) for j, row in enumerate(rows) if j != 1)) for i in range(len(rows[0]))]
    result = []
    for row_index, row in enumerate(rows):
        cells = []
        for cell, width, (left, right) in zip(row, widths, aligns):
            if row_index == 1:
                cell = (":" if left else "") + "-" * (width - left - right) + (":" if right else "")
            else:
                padding = width - _width(cell)
                if left and right:
                    cell = " " * (padding // 2) + cell + " " * (padding - padding // 2)
                else:
                    cell = " " * padding + cell if right else cell + " " * padding
            cells.append(cell)
        result.append(f"{indent}| " + " | ".join(cells) + " |")
    return result


def format_markdown_tables(content: str) -> str:
    """Align tables in MkDocs containers while leaving code blocks untouched."""
    lines = content.split("\n")
    output, containers, fence = [], [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        close = FENCE_CLOSE.match(line)
        if fence:
            if (
                close
                and close.group(2)[0] == fence[0]
                and len(close.group(2)) >= fence[1]
                and len(close.group(1)) <= fence[2]
            ):
                fence = None
            output.append(line)
            i += 1
            continue

        indent = len(line) - len(line.lstrip(" "))
        if line.strip():
            while containers and indent <= containers[-1]:
                containers.pop()
        marker = CONTAINER.match(line[indent:])
        if marker and (indent == 0 or (containers and indent == containers[-1] + 4)):
            containers.append(indent)
        opened = FENCE.match(line)
        base = containers[-1] + 4 if containers else 0
        if opened and base <= indent <= base + 3:
            fence = (opened.group(2)[0], len(opened.group(2)), base + 3)

        row = TABLE_ROW.match(line)
        if row and containers and len(row.group(1)) == containers[-1] + 4:
            end = i + 1
            while end < len(lines) and (next_row := TABLE_ROW.match(lines[end])) and next_row.group(1) == row.group(1):
                end += 1
            output.extend(_align_table(lines[i:end]))
            i = end
        else:
            output.append(line)
            i += 1
    return "\n".join(output)


def extract_code_blocks(markdown_content):
    """Extracts Python and Bash code blocks from Markdown content using regex pattern matching."""
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
    """Formats Python code files in the specified directory using ruff and Python docstring formatter."""
    if not next(Path(temp_dir).rglob("*.py"), None):
        return

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
        # Run ruff check with extra ignored rules:
        # D101 Missing docstring in public class
        # D103 Missing docstring in public function
        # F821 Undefined name
        # F841 Local variable is assigned to but never used
        # Note removed --extend-select=FA to not add 'from future' imports in Python 3.8 environments
        subprocess.run(
            [
                "ruff",
                "check",
                "--fix",
                "--unsafe-fixes",
                "--extend-select=F,I,D,UP,RUF",
                "--target-version=py38",
                "--ignore=B018,BLE001,D100,D101,D103,D104,D203,D205,D212,D213,D401,D406,D407,D413,F821,F841,RUF001,RUF002,RUF012,S110",
                str(temp_dir),
            ],
            check=True,
        )
        print("Completed ruff check ✅")
    except Exception as e:
        print(f"ERROR running ruff check ❌ {e}")

    try:
        # Run Ultralytics Python docstring formatter
        subprocess.run(
            [
                "ultralytics-actions-format-python-docstrings",
                str(temp_dir),
            ],
            check=True,
        )
        print("Completed Python docstring formatting ✅")
    except Exception as e:
        print(f"ERROR running Python docstring formatter ❌ {e}")


def format_bash_with_shfmt(temp_dir):
    """Formats bash script files in the specified directory using shfmt."""
    if not next(Path(temp_dir).rglob("*.sh"), None):
        return

    try:
        # Flags reproduce prettier-plugin-sh output: 2-space indent, spaced redirects, binary ops and cases indented
        result = subprocess.run(
            ["shfmt", "-i", "2", "-sr", "-bn", "-ci", "-w", str(temp_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"ERROR running shfmt ❌ {result.stderr}")
        else:
            print("Completed bash formatting ✅")
    except Exception as e:
        print(f"ERROR running shfmt ❌ {e}")


def process_markdown_string(
    markdown_content: str,
    process_python: bool = True,
    process_bash: bool = True,
    verbose: bool = False,
) -> str:
    """Formats Python/Bash code blocks inside a Markdown string."""
    formatted_markdown = markdown_content
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        temp_md = temp_dir / "input.md"
        temp_md.write_text(markdown_content, encoding="utf-8")

        markdown_snapshot, temp_files = process_markdown_file(temp_md, temp_dir, process_python, process_bash, verbose)
        if markdown_snapshot is None or temp_files is None:
            return formatted_markdown

        python_files_exist = process_python and any(code_type == "python" for _, _, _, code_type in temp_files)
        bash_files_exist = process_bash and any(code_type == "bash" for _, _, _, code_type in temp_files)

        if python_files_exist:
            format_code_with_ruff(temp_dir)
        if bash_files_exist:
            format_bash_with_shfmt(temp_dir)

        update_markdown_file(temp_md, markdown_snapshot, temp_files)
        formatted_markdown = temp_md.read_text(encoding="utf-8")

    return formatted_markdown


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
    """Processes a Markdown file, extracting code blocks into temp files and returning the content and file info."""
    try:
        markdown_content = Path(file_path).read_text(encoding="utf-8")
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

                with open(temp_file_path, "w", encoding="utf-8") as temp_file:
                    temp_file.write(f"{code_without_indentation}\n")

                temp_files.append((num_spaces, code_block, temp_file_path, code_type))

        return markdown_content, temp_files

    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return None, None


def update_markdown_file(file_path, markdown_content, temp_files):
    """Updates a Markdown file with formatted code blocks."""
    for num_spaces, original_code_block, temp_file_path, code_type in temp_files:
        try:
            with open(temp_file_path, encoding="utf-8") as temp_file:
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
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(markdown_content)
    except Exception as e:
        print(f"Error writing file {file_path}: {e}")


def main(root_dir=None, process_python=True, process_bash=True, verbose=False):
    """Processes Markdown files, extracts and formats code blocks, and updates the original files."""
    root_path = Path.cwd() if root_dir is None else Path(root_dir)
    markdown_files = [markdown_file for markdown_file in root_path.rglob("*.md") if not markdown_file.is_symlink()]
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
        if markdown_content:
            formatted_markdown = (
                markdown_content if "reference" in markdown_file.parts else format_markdown_tables(markdown_content)
            )
            if temp_files or formatted_markdown != markdown_content:
                all_temp_files.append((markdown_file, formatted_markdown, temp_files))

    # Format code blocks based on flags
    if process_python:
        format_code_with_ruff(temp_dir)  # Format Python files
    if process_bash:
        format_bash_with_shfmt(temp_dir)  # Format Bash files

    # Update Markdown files with formatted code blocks
    for markdown_file, markdown_content, temp_files in all_temp_files:
        update_markdown_file(markdown_file, markdown_content, temp_files)

    # Clean up temp directory
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main(process_python=True, process_bash=True)
