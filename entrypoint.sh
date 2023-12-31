#!/bin/sh -l

# Format Python code
echo "Running Ruff for Python code formatting..."
ruff .

# Format markdown files
echo "Running mdformat for Markdown formatting..."
mdformat .

# Format Python docstrings
echo "Running docformatter..."
docformatter -i -r .

# Run spell check
echo "Running codespell for spell checking..."
codespell -w

# Commit and push changes
echo "Committing and pushing changes..."
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
git add -A
git commit -m "Auto-format by Ultralytics action" || echo "No changes to commit"
git push
