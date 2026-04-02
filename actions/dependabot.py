# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Update GitHub Actions versions across organization repositories with cached version resolution."""

import base64
import json
import os
import re
import subprocess
import time

import requests

# Matches: `uses: owner/repo@ref` or `uses: owner/repo/path@ref` with optional `# comment`
USES_PATTERN = re.compile(
    r"^(?P<indent>\s*-?\s*uses:\s*)(?P<action>[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?)@(?P<ref>\S+?)(?P<comment>\s+#\s*.+)?$",
    re.MULTILINE,
)


def is_sha(ref):
    """Check if a reference is a full SHA (40 hex chars)."""
    return bool(re.fullmatch(r"[0-9a-f]{40}", ref))


def is_branch(ref):
    """Check if a reference is likely a branch name (not a version tag or SHA)."""
    if is_sha(ref):
        return False
    # Version tags start with 'v' followed by a digit, or are pure digits with dots
    if re.match(r"^v?\d", ref):
        return False
    # Common release patterns like 'release/v1'
    if "release" in ref:
        return False
    # Everything else (main, master, develop, etc.) is a branch
    return True


def get_major_version(tag):
    """Extract major version from a tag like 'v6', 'v6.0.1', 'v2.8.0'."""
    m = re.match(r"^v(\d+)", tag)
    return int(m.group(1)) if m else None


def get_latest_release(action, token, cache):
    """Get latest release tag and its commit SHA for an action, using cache.

    Args:
        action: Action name like 'actions/checkout' (without path suffixes).
        token: GitHub token for API auth.
        cache: Dict mapping action -> {tag, sha} to accumulate across repos.

    Returns:
        Dict with 'tag' and 'sha' keys, or None if lookup fails.
    """
    # Strip path suffixes (e.g. 'ultralytics/actions/scan-prs' -> 'ultralytics/actions')
    repo = "/".join(action.split("/")[:2])

    if repo in cache:
        return cache[repo]

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    # Try releases/latest first (most actions use GitHub releases)
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
    if r.status_code == 200:
        tag = r.json().get("tag_name", "")
        if tag:
            sha = resolve_tag_sha(repo, tag, headers)
            cache[repo] = {"tag": tag, "sha": sha}
            print(f"  Cached {repo}: {tag} ({sha[:8]})" if sha else f"  Cached {repo}: {tag}")
            return cache[repo]

    # Fallback to tags (sorted by semver-like ordering)
    r = requests.get(f"https://api.github.com/repos/{repo}/tags?per_page=1", headers=headers)
    if r.status_code == 200:
        tags = r.json()
        if tags:
            tag = tags[0]["name"]
            sha = tags[0]["commit"]["sha"]
            cache[repo] = {"tag": tag, "sha": sha}
            print(f"  Cached {repo}: {tag} ({sha[:8]})")
            return cache[repo]

    print(f"  Could not resolve latest version for {repo}")
    return None


def resolve_tag_sha(repo, tag, headers):
    """Resolve a tag to its commit SHA (handles annotated tags)."""
    r = requests.get(f"https://api.github.com/repos/{repo}/git/ref/tags/{tag}", headers=headers)
    if r.status_code != 200:
        return None
    obj = r.json().get("object", {})
    # If annotated tag, dereference to commit
    if obj.get("type") == "tag":
        r2 = requests.get(obj["url"], headers=headers)
        if r2.status_code == 200:
            return r2.json().get("object", {}).get("sha")
    return obj.get("sha")


def compute_update(current_ref, comment, latest):
    """Determine the updated ref and comment for an action line.

    Returns (new_ref, new_comment) or None if no update needed.
    """
    if not latest:
        return None

    latest_tag = latest["tag"]
    latest_sha = latest["sha"]

    if is_sha(current_ref):
        # SHA pinned: update to latest SHA and tag comment
        if current_ref == latest_sha:
            return None
        new_comment = f" # {latest_tag}"
        return latest_sha, new_comment

    # Tag reference: check if there's a newer version
    current_major = get_major_version(current_ref)
    latest_major = get_major_version(latest_tag)
    if current_major is None or latest_major is None:
        return None

    # Check if using major-only tag (e.g., 'v6') vs specific (e.g., 'v6.0.1')
    is_major_only = re.fullmatch(r"v\d+", current_ref)

    if is_major_only:
        # Using major tag like @v6 -> update to latest major @v7
        if latest_major > current_major:
            return f"v{latest_major}", comment
    else:
        # Using specific tag like @v2.8.0 -> update to latest tag
        if current_ref != latest_tag:
            return latest_tag, comment

    return None


def update_workflow_content(content, token, cache):
    """Update action versions in workflow file content.

    Returns (updated_content, list_of_changes) where changes are dicts describing each update.
    """
    changes = []

    def replace_match(m):
        indent = m.group("indent")
        action = m.group("action")
        ref = m.group("ref")
        comment = m.group("comment") or ""

        if is_branch(ref):
            return m.group(0)  # Leave branch refs alone

        latest = get_latest_release(action, token, cache)
        result = compute_update(ref, comment, latest)
        if result is None:
            return m.group(0)

        new_ref, new_comment = result
        changes.append({"action": action, "old": f"{ref}{comment}", "new": f"{new_ref}{new_comment}"})
        return f"{indent}{action}@{new_ref}{new_comment}"

    updated = USES_PATTERN.sub(replace_match, content)
    return updated, changes


def get_workflow_files(org, repo, token):
    """Fetch workflow file paths and action.yml from a repo using the GitHub API."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    files = []

    # Check .github/workflows/
    r = requests.get(f"https://api.github.com/repos/{org}/{repo}/contents/.github/workflows", headers=headers)
    if r.status_code == 200:
        files.extend(
            f["path"] for f in r.json() if isinstance(f, dict) and f.get("name", "").endswith((".yml", ".yaml"))
        )

    # Check action.yml and action.yaml at root
    for name in ("action.yml", "action.yaml"):
        r = requests.get(f"https://api.github.com/repos/{org}/{repo}/contents/{name}", headers=headers)
        if r.status_code == 200:
            files.append(name)

    return files


def get_file_content(org, repo, path, token):
    """Fetch raw file content from a repo."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3.raw"}
    r = requests.get(f"https://api.github.com/repos/{org}/{repo}/contents/{path}", headers=headers)
    return r.text if r.status_code == 200 else None


def make_pr_title(action, old_ref, new_ref, path):
    """Generate a Dependabot-style PR title for an action update.

    Example: 'Bump actions/checkout from v5 to v6 in /.github/workflows'
    """
    old_ver = old_ref.split("#")[-1].strip() if "#" in old_ref else old_ref
    new_ver = new_ref.split("#")[-1].strip() if "#" in new_ref else new_ref
    location = f"/{os.path.dirname(path)}" if "/" in path else "/"
    return f"Bump {action} from {old_ver} to {new_ver} in {location}"


def get_open_pr_titles(org, repo):
    """Get titles of all open PRs in a repo using gh CLI."""
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", f"{org}/{repo}", "--state", "open", "--json", "title", "--limit", "100"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return {pr["title"] for pr in json.loads(result.stdout)}


def create_single_pr(org, repo, title, file_path, new_content, token):
    """Create a single PR updating one file.

    Returns:
        PR URL if created, None otherwise.
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    # Get default branch and its HEAD SHA
    r = requests.get(f"https://api.github.com/repos/{org}/{repo}", headers=headers)
    if r.status_code != 200:
        return None
    default_branch = r.json()["default_branch"]

    r = requests.get(f"https://api.github.com/repos/{org}/{repo}/git/ref/heads/{default_branch}", headers=headers)
    if r.status_code != 200:
        return None
    base_sha = r.json()["object"]["sha"]

    # Create branch from title slug
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:60]
    branch = f"dependabot/github_actions/{slug}"

    r = requests.post(
        f"https://api.github.com/repos/{org}/{repo}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )
    if r.status_code not in (200, 201):
        print(f"    Failed to create branch: {r.json().get('message', '')}")
        return None

    # Update file
    r = requests.get(f"https://api.github.com/repos/{org}/{repo}/contents/{file_path}", headers=headers)
    if r.status_code != 200:
        return None
    file_sha = r.json()["sha"]

    r = requests.put(
        f"https://api.github.com/repos/{org}/{repo}/contents/{file_path}",
        headers=headers,
        json={
            "message": title,
            "content": base64.b64encode(new_content.encode()).decode(),
            "sha": file_sha,
            "branch": branch,
        },
    )
    if r.status_code not in (200, 201):
        print(f"    Failed to update {file_path}: {r.json().get('message', '')}")
        return None

    # Create PR
    r = requests.post(
        f"https://api.github.com/repos/{org}/{repo}/pulls",
        headers=headers,
        json={
            "title": title,
            "body": f"{title}\n\nAutomated by [Ultralytics Actions](https://github.com/ultralytics/actions).",
            "head": branch,
            "base": default_branch,
        },
    )
    if r.status_code in (200, 201):
        return r.json().get("html_url")
    print(f"    Failed to create PR: {r.json().get('message', '')}")
    return None


def run():
    """Update GitHub Actions versions across organization repos with cached lookups."""
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    org = os.getenv("ORG", "ultralytics")

    if not token:
        print("Error: GH_TOKEN or GITHUB_TOKEN required")
        return

    # Build visibility filter from env vars (all on by default)
    visibility = {v for v in ("public", "private", "internal") if os.getenv(v.upper(), "true").lower() == "true"}
    if not visibility:
        print("⚠️  No visibility selected, defaulting to all")
        visibility = {"public", "private", "internal"}
    print(f"🔍 Scanning {', '.join(sorted(visibility))} repos in {org} for outdated GitHub Actions...")

    # Get active repos across all visibilities
    result = subprocess.run(
        ["gh", "repo", "list", org, "--limit", "1000", "--json", "name,isArchived,visibility"],
        capture_output=True,
        text=True,
        check=True,
    )
    repos = sorted(
        r["name"] for r in json.loads(result.stdout) if not r["isArchived"] and r["visibility"].lower() in visibility
    )
    print(f"Found {len(repos)} active repos\n")

    # Cache: maps 'owner/repo' -> {'tag': 'v6.0.1', 'sha': 'abc...'} (accumulated across all repos)
    cache = {}
    summary = []
    total_prs_created = 0
    total_prs_skipped = 0

    for repo_name in repos:
        print(f"📦 {org}/{repo_name}")

        # Get workflow files
        workflow_files = get_workflow_files(org, repo_name, token)
        if not workflow_files:
            print("  No workflow files found")
            continue

        # Get existing open PR titles to avoid duplicates
        open_titles = get_open_pr_titles(org, repo_name)

        # Process each file, creating one PR per action update
        for path in workflow_files:
            content = get_file_content(org, repo_name, path, token)
            if not content:
                continue

            # Check each action reference individually
            for m in USES_PATTERN.finditer(content):
                action = m.group("action")
                ref = m.group("ref")
                comment = m.group("comment") or ""

                if is_branch(ref):
                    continue

                latest = get_latest_release(action, token, cache)
                result = compute_update(ref, comment, latest)
                if result is None:
                    continue

                new_ref, new_comment = result
                title = make_pr_title(action, f"{ref}{comment}", f"{new_ref}{new_comment}", path)

                # Skip if a PR with the same title already exists
                if title in open_titles:
                    print(f"  ⏭️  {title} (PR already exists)")
                    total_prs_skipped += 1
                    continue

                print(f"  {path}: {action} {ref}{comment} -> {new_ref}{new_comment}")

                # Apply this single update using match position (not str.replace)
                new_line = f"{m.group('indent')}{action}@{new_ref}{new_comment}"
                updated_content = content[: m.start()] + new_line + content[m.end() :]

                pr_url = create_single_pr(org, repo_name, title, path, updated_content, token)
                if pr_url:
                    print(f"    ✅ Created PR: {pr_url}")
                    summary.append(f"- ✅ [{org}/{repo_name}]({pr_url}): {title}")
                    open_titles.add(title)  # Prevent duplicate within same run
                    total_prs_created += 1
                else:
                    print(f"    ❌ Failed to create PR")

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"📊 Done! Created {total_prs_created} PRs | Skipped {total_prs_skipped} (already open)")
    print(f"Cached {len(cache)} action versions (saved ~{max(0, len(repos) * len(cache) - len(cache))} API lookups)")

    if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
        lines = [
            "# 🔄 Dependabot - Update GitHub Actions\n",
            f"**Repos scanned:** {len(repos)} | **PRs created:** {total_prs_created} | **Skipped:** {total_prs_skipped} | **Actions cached:** {len(cache)}\n",
            *summary,
        ]
        with open(summary_file, "a") as f:
            f.write("\n".join(lines))


if __name__ == "__main__":
    run()
