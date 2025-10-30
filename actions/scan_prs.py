# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""List and auto-merge open PRs across GitHub organization."""

import json
import os
import subprocess
from datetime import datetime, timezone


def get_age_days(created_at):
    """Calculate PR age in days from ISO timestamp."""
    return (datetime.now(timezone.utc) - datetime.fromisoformat(created_at.replace("Z", "+00:00"))).days


def get_phase_emoji(age_days):
    """Return emoji and label for PR age phase."""
    if age_days == 0:
        return "🆕", "NEW"
    elif age_days <= 7:
        return "🟢", f"{age_days} days"
    elif age_days <= 30:
        return "🟡", f"{age_days} days"
    else:
        return "🔴", f"{age_days} days"


def run():
    """List open PRs across organization and auto-merge eligible Dependabot PRs."""
    # Get and validate settings
    org = os.getenv("ORG", "ultralytics")
    visibility = os.getenv("VISIBILITY", "public").lower()
    repo_visibility = os.getenv("REPO_VISIBILITY", "public").lower()
    valid_visibilities = {"public", "private", "internal", "all"}

    if visibility not in valid_visibilities:
        print(f"⚠️  Invalid visibility '{visibility}', defaulting to 'public'")
        visibility = "public"

    # Security: if calling repo is public, restrict to public repos only
    if repo_visibility == "public" and visibility != "public":
        print(f"⚠️  Security: Public repo cannot scan {visibility} repos. Restricting to public only.")
        visibility = "public"

    print(f"🔍 Scanning {visibility} repositories in {org} organization...")

    # Get active repos with specified visibility
    cmd = ["gh", "repo", "list", org, "--limit", "1000", "--json", "name,url,isArchived"]
    if visibility != "all":
        cmd.extend(["--visibility", visibility])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    repos = {r["name"]: r["url"] for r in json.loads(result.stdout) if not r["isArchived"]}

    if not repos:
        print("⚠️  No repositories found")
        return

    # Get all open PRs
    result = subprocess.run(
        [
            "gh",
            "search",
            "prs",
            "--owner",
            org,
            "--state",
            "open",
            "--limit",
            "1000",
            "--json",
            "repository,number,title,url,createdAt",
            "--sort",
            "created",
            "--order",
            "desc",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    all_prs = json.loads(result.stdout)

    if not all_prs:
        print("✅ No open PRs found")
        return

    # Count PRs by phase
    phase_counts = {"new": 0, "green": 0, "yellow": 0, "red": 0}
    for pr in all_prs:
        age_days = get_age_days(pr["createdAt"])
        phase_counts[
            "new" if age_days == 0 else "green" if age_days <= 7 else "yellow" if age_days <= 30 else "red"
        ] += 1

    repo_count = len({pr["repository"]["name"] for pr in all_prs if pr["repository"]["name"] in repos})
    summary = [
        f"# 🔍 Open Pull Requests - {org.title()} Organization\n",
        f"**Total:** {len(all_prs)} open PRs across {repo_count} repos",
        f"**By Phase:** 🆕 {phase_counts['new']} New | 🟢 {phase_counts['green']} Green (≤7d) | 🟡 {phase_counts['yellow']} Yellow (≤30d) | 🔴 {phase_counts['red']} Red (>30d)\n",
    ]

    for repo_name in sorted({pr["repository"]["name"] for pr in all_prs}):
        if repo_name not in repos:
            continue

        repo_prs = [pr for pr in all_prs if pr["repository"]["name"] == repo_name]
        summary.append(
            f"## 📦 [{repo_name}]({repos[repo_name]}) - {len(repo_prs)} open PR{'s' if len(repo_prs) > 1 else ''}"
        )

        for pr in repo_prs[:30]:
            emoji, age_str = get_phase_emoji(get_age_days(pr["createdAt"]))
            summary.append(f"- 🔀 [#{pr['number']}]({pr['url']}) {pr['title']} {emoji} {age_str}")

        if len(repo_prs) > 30:
            summary.append(f"- ... {len(repo_prs) - 30} more PRs")
        summary.append("")

    # Auto-merge Dependabot GitHub Actions PRs
    print("\n🤖 Checking for Dependabot PRs to auto-merge...")
    summary.append("\n# 🤖 Auto-Merge Dependabot GitHub Actions PRs\n")
    total_found = total_merged = total_skipped = 0

    for repo_name in repos:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                f"{org}/{repo_name}",
                "--author",
                "app/dependabot",
                "--state",
                "open",
                "--json",
                "number,title,files,mergeable,statusCheckRollup",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            continue

        merged = 0
        for pr in json.loads(result.stdout):
            if not all(f["path"].startswith(".github/workflows/") for f in pr["files"]):
                continue

            total_found += 1
            pr_ref = f"{org}/{repo_name}#{pr['number']}"
            print(f"  Found: {pr_ref} - {pr['title']}")

            if merged >= 1:
                print(f"    ⏭️  Skipped (already merged 1 PR in {repo_name})")
                total_skipped += 1
                continue

            if pr["mergeable"] != "MERGEABLE":
                print(f"    ❌ Skipped (not mergeable: {pr['mergeable']})")
                total_skipped += 1
                continue

            # Check if all status checks passed (empty list or None = no checks = pass)
            checks = pr.get("statusCheckRollup") or []
            failed_checks = [c for c in checks if c.get("conclusion") not in ["SUCCESS", "SKIPPED", "NEUTRAL", None]]

            if failed_checks:
                for check in failed_checks:
                    print(f"    ❌ Failing check: {check.get('name', 'unknown')} = {check.get('conclusion')}")
                total_skipped += 1
                continue

            print("    ✅ All checks passed, merging...")
            result = subprocess.run(
                ["gh", "pr", "merge", str(pr["number"]), "--repo", f"{org}/{repo_name}", "--squash", "--admin"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"    ✅ Successfully merged {pr_ref}")
                summary.append(f"- ✅ Merged {pr_ref}")
                total_merged += 1
                merged += 1
            else:
                print(f"    ❌ Merge failed: {result.stderr.strip()}")
                total_skipped += 1

    summary.append(f"\n**Summary:** Found {total_found} | Merged {total_merged} | Skipped {total_skipped}")
    print(f"\n📊 Dependabot Summary: Found {total_found} | Merged {total_merged} | Skipped {total_skipped}")

    # Write to GitHub step summary if available
    if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a") as f:
            f.write("\n".join(summary))


if __name__ == "__main__":
    run()
