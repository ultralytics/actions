#!/bin/sh -l

# Configure Git
git config --global user.name "glenn-jocher"
git config --global user.email "glenn-jocher@ultralytics.com"
git config --global --add safe.directory /github/workspace

# Run formatting tools
echo "Running Ruff for Python code formatting..."
ruff .

echo "Running mdformat for Markdown formatting..."
mdformat .

echo "Running docformatter..."
docformatter -i -r .

echo "Running codespell for spell checking..."
codespell -w

# Staging the changes
git add -A

# Check if there are any changes to commit
if git diff --staged --quiet; then
    echo "No changes to commit"
    exit 0
fi

# Determine the current branch or fallback to main if not available
BRANCH=${GITHUB_REF##*/}

# For pull requests, GITHUB_HEAD_REF is set
if [ -n "$GITHUB_HEAD_REF" ]; then
    BRANCH=$GITHUB_HEAD_REF
fi

# Committing changes
git commit -m "Auto-format by Ultralytics action"

# Fetch the latest updates from the remote
git fetch origin

# Check if the remote branch is ahead
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/$BRANCH)
if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
    echo "Remote branch is ahead. Skipping push to avoid conflicts."
    exit 0
fi

# Push changes
git push origin HEAD:$BRANCH
