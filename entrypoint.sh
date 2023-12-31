#!/bin/sh -l

# Configure Git
git config --global user.name "glenn-jocher"
git config --global user.email "glenn.jocher@ultralytics.com"
git config --global --add safe.directory /github/workspace

# Fetch all history for all branches and tags
git fetch --no-tags --prune --depth=1 origin +refs/heads/*:refs/remotes/origin/*

# Determine the branch name
BRANCH=${GITHUB_REF##*/}
if [ -n "$GITHUB_HEAD_REF" ]; then
    BRANCH=$GITHUB_HEAD_REF
fi

# Checkout a local branch based on the PR branch
git checkout -B $BRANCH origin/$BRANCH

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

# Committing changes
git commit -m "Auto-format by Ultralytics action"

# Push changes
git push origin $BRANCH
