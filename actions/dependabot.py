# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Update GitHub Actions versions across organization repositories with cached version resolution."""

import json
import os
import re
import subprocess

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
    return not is_sha(ref) and not re.match(r"^v?\d", ref) and "release" not in ref


def parse_version(ref):
    """Extract a comparable numeric version tuple from a tag-like ref."""
    numbers = tuple(int(part) for part in re.findall(r"\d+", ref))
    return numbers or None


def get_latest_release(action, token, cache):
    """Get latest release tag and its commit SHA for an action, using cache."""
    repo = "/".join(action.split("/")[:2])
    if repo in cache:
        return cache[repo]

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
    if r.status_code != 200:
        print(f"  Could not resolve latest version for {repo}")
        return None

    tag = r.json().get("tag_name", "")
    if not tag:
        return None

    # Resolve tag to commit SHA (handles annotated tags)
    sha = None
    r2 = requests.get(f"https://api.github.com/repos/{repo}/git/ref/tags/{tag}", headers=headers)
    if r2.status_code == 200:
        obj = r2.json().get("object", {})
        if obj.get("type") == "tag":
            r3 = requests.get(obj["url"], headers=headers)
            sha = r3.json().get("object", {}).get("sha") if r3.status_code == 200 else None
        else:
            sha = obj.get("sha")

    # Check if the major-only tag exists (e.g., 'v8' for release 'v8.0.0')
    major_match = re.match(r"^(v?)(\d+)", tag)
    major_tag = f"{major_match.group(1)}{major_match.group(2)}" if major_match else None
    has_major_tag = False
    if major_tag and major_tag != tag:
        r3 = requests.get(f"https://api.github.com/repos/{repo}/git/ref/tags/{major_tag}", headers=headers)
        has_major_tag = r3.status_code == 200

    cache[repo] = {"tag": tag, "sha": sha, "major_tag": major_tag if has_major_tag else None}
    print(f"  Cached {repo}: {tag} ({sha[:8]})" if sha else f"  Cached {repo}: {tag}")
    return cache[repo]


def compute_update(current_ref, comment, latest):
    """Determine the updated ref and comment for an action line.

    Returns (new_ref, new_comment) or None if no update needed.
    """
    if not latest:
        return None

    latest_tag = latest["tag"]
    latest_sha = latest["sha"]

    if is_sha(current_ref):
        if not latest_sha or current_ref == latest_sha:
            return None
        return latest_sha, f" # {latest_tag}"

    # Tag reference: check if there's a newer version
    current_major = re.match(r"^v?(\d+)", current_ref)
    latest_major = re.match(r"^v?(\d+)", latest_tag)
    if not current_major or not latest_major:
        return None

    if re.fullmatch(r"v?\d+", current_ref):
        # Major-only tag like @v6 -> update to @v8 only if that tag actually exists.
        if int(latest_major.group(1)) > int(current_major.group(1)) and latest.get("major_tag"):
            return latest["major_tag"], comment
    elif current_ref != latest_tag:
        # Specific tag like @v2.8.0 -> update to the latest tag only when it is semantically newer.
        current_version = parse_version(current_ref)
        latest_version = parse_version(latest_tag)
        if current_version and latest_version and latest_version > current_version:
            return latest_tag, comment

    return None


def get_workflow_files(org, repo, token):
    """Fetch workflow file paths and action.yml from a repo using the GitHub API."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    files = []

    r = requests.get(f"https://api.github.com/repos/{org}/{repo}/contents/.github/workflows", headers=headers)
    if r.status_code == 200:
        files.extend(
            f["path"] for f in r.json() if isinstance(f, dict) and f.get("name", "").endswith((".yml", ".yaml"))
        )

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


def make_pr_title(action, new_ref):
    """Generate a Dependabot-style PR title for an action update."""
    new_ver = new_ref.split("#")[-1].strip() if "#" in new_ref else new_ref
    return f"Bump {action} to {new_ver} in /.github/workflows"


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


def create_pr(org, repo, title, file_updates, token):
    """Create a PR with a single commit updating one or more files using the Git Data API."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{org}/{repo}"

    # Get default branch and its HEAD commit SHA
    r = requests.get(api, headers=headers)
    if r.status_code != 200:
        return None
    default_branch = r.json()["default_branch"]

    r = requests.get(f"{api}/git/ref/heads/{default_branch}", headers=headers)
    if r.status_code != 200:
        return None
    base_sha = r.json()["object"]["sha"]

    # Get base tree SHA
    r = requests.get(f"{api}/git/commits/{base_sha}", headers=headers)
    if r.status_code != 200:
        return None
    base_tree_sha = r.json()["tree"]["sha"]

    # Create blobs for each file and build tree entries
    tree_entries = []
    for path, content in file_updates:
        r = requests.post(f"{api}/git/blobs", headers=headers, json={"content": content, "encoding": "utf-8"})
        if r.status_code not in (200, 201):
            print(f"    Failed to create blob for {path}, aborting PR")
            return None
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": r.json()["sha"]})

    # Create tree
    r = requests.post(f"{api}/git/trees", headers=headers, json={"base_tree": base_tree_sha, "tree": tree_entries})
    if r.status_code not in (200, 201):
        print(f"    Failed to create tree: {r.json().get('message', '')}")
        return None
    tree_sha = r.json()["sha"]

    # Create single commit
    r = requests.post(
        f"{api}/git/commits",
        headers=headers,
        json={"message": title, "tree": tree_sha, "parents": [base_sha]},
    )
    if r.status_code not in (200, 201):
        print(f"    Failed to create commit: {r.json().get('message', '')}")
        return None
    commit_sha = r.json()["sha"]

    # Create branch pointing to the commit
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:60]
    branch = f"dependabot/github_actions/{slug}"
    r = requests.post(f"{api}/git/refs", headers=headers, json={"ref": f"refs/heads/{branch}", "sha": commit_sha})
    if r.status_code not in (200, 201):
        print(f"    Failed to create branch: {r.json().get('message', '')}")
        return None

    # Create PR
    r = requests.post(
        f"{api}/pulls",
        headers=headers,
        json={
            "title": title,
            "body": (
                f"{title}\n\n"
                "This PR updates GitHub Actions references in this repository.\n\n"
                "Examples:\n"
                "- Branch: `actions/checkout@main` stays on `@main`\n"
                "- Major tag: `actions/checkout@v4` updates to `@v5`\n"
                "- Specific tag: `astral-sh/setup-uv@v0.5.0` updates to `@v0.9.4`\n"
                "- SHA pinned: `actions/checkout@<sha> # v4.1.0` updates to the latest release SHA and tag comment\n\n"
                "<sub>Made with ❤️ by [Ultralytics Actions](https://www.ultralytics.com/actions)</sub>"
            ),
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
        visibility = {"public", "private", "internal"}
    print(f"🔍 Scanning {', '.join(sorted(visibility))} repos in {org} for outdated GitHub Actions...")

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

    cache = {}
    summary = []
    total_prs_created = 0
    total_prs_skipped = 0

    for repo_name in repos:
        print(f"📦 {org}/{repo_name}")

        workflow_files = get_workflow_files(org, repo_name, token)
        if not workflow_files:
            print("  No workflow files found")
            continue

        # Phase 1: collect all updates grouped by (action, new_ref) across all files
        # Key: (action_base_repo, new_ref) -> {title, file_contents: {path: content}}
        updates = {}
        file_cache = {}  # path -> original content

        for path in workflow_files:
            content = get_file_content(org, repo_name, path, token)
            if not content:
                continue
            file_cache[path] = content

            for m in USES_PATTERN.finditer(content):
                action = m.group("action")
                ref = m.group("ref")
                comment = m.group("comment") or ""

                if is_branch(ref):
                    continue

                latest = get_latest_release(action, token, cache)
                update = compute_update(ref, comment, latest)
                if update is None:
                    continue

                new_ref, new_comment = update
                key = ("/".join(action.split("/")[:2]), new_ref)

                if key not in updates:
                    updates[key] = {"new_ref": new_ref, "new_comment": new_comment, "replacements": []}
                updates[key]["replacements"].append(
                    (path, m.start(), m.end(), m.group("indent"), action, new_ref, new_comment)
                )

        if not updates:
            continue

        # Phase 2: create one PR per action update
        open_titles = get_open_pr_titles(org, repo_name)

        for (action_repo, new_ref), info in updates.items():
            title = make_pr_title(action_repo, f"{new_ref}{info['new_comment']}")

            if title in open_titles:
                print(f"  ⏭️  {title} (PR already exists)")
                total_prs_skipped += 1
                continue

            # Apply replacements per file in reverse position order to preserve offsets
            file_updates = {}
            for path, start, end, indent, action, nref, ncomment in sorted(
                info["replacements"], key=lambda x: x[1], reverse=True
            ):
                content = file_updates.get(path, file_cache[path])
                new_line = f"{indent}{action}@{nref}{ncomment}"
                file_updates[path] = content[:start] + new_line + content[end:]
                print(f"  {path}: {action} -> {nref}{ncomment}")

            pr_url = create_pr(org, repo_name, title, list(file_updates.items()), token)
            if pr_url:
                print(f"    ✅ Created PR: {pr_url}")
                summary.append(f"- ✅ [{org}/{repo_name}]({pr_url}): {title}")
                open_titles.add(title)
                total_prs_created += 1
            else:
                print("    ❌ Failed to create PR")

    print(f"\n📊 Done! Created {total_prs_created} PRs | Skipped {total_prs_skipped} (already open)")
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
