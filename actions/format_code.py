# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import os
import subprocess

# Mirrors the formatting steps in action.yml (source of truth if these drift); tested in tests/test_format_code.py
RUFF_CHECK = [
    "ruff",
    "check",
    "--fix",
    "--unsafe-fixes",
    "--extend-select=F,I,D,UP,RUF,FA",
    "--ignore=BLE001,D100,D104,D203,D205,D212,D213,D401,D406,D407,D413,RUF001,RUF002,RUF012,S110",
    ".",
]
RUFF_FORMAT = ["ruff", "format", "--line-length=120", "."]
DOCSTRINGS = ["ultralytics-actions-format-python-docstrings", "."]
PRETTIER = """
npm install -g prettier@3.6.2 prettier-plugin-sh
ultralytics-actions-update-markdown-code-blocks
npx prettier --write --list-different --print-width 120 "**/*.{js,jsx,ts,tsx,css,less,scss,json,yml,yaml,html,vue,svelte}" '!**/*lock.{json,yaml,yml}' '!**/*.lock' '!**/model.json' '!**/*.min.js' '!**/*.min.css'
if find . -name "*.sh" -type f | grep -q .; then
    npx prettier --write --list-different --print-width 120 --plugin=$(npm root -g)/prettier-plugin-sh/lib/index.cjs "**/*.sh"
fi
# Handle Markdown separately
find . -name "*.md" -type f ! -path "*/docs/*" -exec npx prettier --write --list-different --print-width 120 {} +
if [ -d "./docs" ]; then
    find ./docs -name "*.md" -type f ! -path "*/reference/*" -exec npx prettier --tab-width 4 --print-width 120 --write --list-different {} +
fi
"""
CODESPELL = [
    "codespell",
    "--builtin",
    "clear,informal,en-GB_to_en-US",
    "--write-changes",
    "--uri-ignore-words-list",
    "*",
    "--ignore-regex",
    r"\b[a-z]+[A-Z][a-zA-Z]*\b",
    "--ignore-words-list",
    "nin,cancelled,MapPin,couldn,grey,writeable,RepResNet,Idenfy,Smoot,EHR,ALS,Carmel,FPR,Hach,Calle,crate,nd,ned,strack,dota,ane,segway,fo,gool,winn,nam,afterall,skelton,goin,cann,CANN",
    "--skip",
    "*.pt,*.pth,*.torchscript,*.onnx,*.tflite,*.pb,*.bin,*.param,*.mlmodel,*.engine,*.npy,*.data*,*.csv,*pnnx*,*venv*,*translat*,*lock*,__pycache__*,*.ico,*.jpg,*.png,*.webp,*.avif,*.mp4,*.mov,/runs,/.git,./docs/??/*.md,./docs/mkdocs_??.yml,action.yml",
]


def _enabled(name: str) -> bool:
    """Check an INPUTS_* env flag, defaulting to enabled."""
    return os.getenv(name, "true").lower() == "true"


def _run(cmd, shell: bool = False) -> None:
    """Run one formatter, continuing on failure like the composite action steps."""
    try:
        subprocess.run(cmd, shell=shell, check=True)
    except Exception as e:
        print(f"Formatter {'script' if shell else cmd[0]} failed but continuing: {e}")


def main():
    """Format the current directory with the Ultralytics Actions formatters (Python, Prettier, Codespell)."""
    if _enabled("INPUTS_PYTHON"):
        _run(RUFF_CHECK)
        _run(RUFF_FORMAT)
        if _enabled("INPUTS_PYTHON_DOCSTRINGS"):
            _run(DOCSTRINGS)
    if _enabled("INPUTS_PRETTIER"):
        _run(PRETTIER, shell=True)
    if _enabled("INPUTS_SPELLING"):
        _run(CODESPELL)


if __name__ == "__main__":
    main()
