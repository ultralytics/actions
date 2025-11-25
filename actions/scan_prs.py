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


def parse_visibility(visibility_input, repo_visibility):
    """Parse and validate visibility settings with security checks."""
    valid = {"public", "private", "internal", "all"}
    stripped = [v.strip() for v in visibility_input.lower().split(",") if v.strip()]
    repo_visibility = (repo_visibility or "").lower()

    # Warn about invalid values
    if invalid := [v for v in stripped if v not in valid]:
        print(f"⚠️  Invalid visibility values: {', '.join(invalid)} - ignoring")

    visibility_list = [v for v in stripped if v in valid]
    if not visibility_list:
        print("⚠️  No valid visibility values, defaulting to 'public'")
        return ["public"]

    # Security: public repos can only scan public repos
    if repo_visibility == "public" and visibility_list != ["public"]:
        print("⚠️  Security: Public repo cannot scan non-public repos. Restricting to public only.")
        return ["public"]

    return visibility_list


def get_repo_filter(visibility_list):
    """Return filtering strategy for repo visibility."""
    if len(visibility_list) == 1 and visibility_list[0] != "all":
        return {"flag": ["--visibility", visibility_list[0]], "filter": None, "str": visibility_list[0]}

    filter_set = {"public", "private", "internal"} if "all" in visibility_list else set(visibility_list)
    return {
        "flag": [],
        "filter": filter_set,
        "str": "all" if "all" in visibility_list else ", ".join(sorted(visibility_list)),
    }


def get_status_checks(rollup):
    """Extract and validate status checks from rollup, return failed checks."""
    checks = rollup if isinstance(rollup, list) else rollup.get("contexts", []) if isinstance(rollup, dict) else []
    return [
        c
        for c in checks
        if (s := (c.get("conclusion") or c.get("state") or "").upper()) and s not in {"SUCCESS", "SKIPPED", "NEUTRAL"}
    ]


def run():
    """List open PRs across organization and auto-merge eligible Dependabot PRs."""
    org = os.getenv("ORG", "ultralytics")
    visibility_list = parse_visibility(os.getenv("VISIBILITY", "public"), os.getenv("REPO_VISIBILITY", "public"))
    filter_config = get_repo_filter(visibility_list)

    print(f"🔍 Scanning {filter_config['str']} repositories in {org} organization...")

    # Get active repos
    result = subprocess.run(
        ["gh", "repo", "list", org, "--limit", "1000", "--json", "name,url,isArchived,visibility"]
        + filter_config["flag"],
        capture_output=True,
        text=True,
        check=True,
    )
    all_repos = [r for r in json.loads(result.stdout) if not r["isArchived"]]
    repos = {
        r["name"]: r["url"]
        for r in all_repos
        if not filter_config["filter"] or r["visibility"].lower() in filter_config["filter"]
    }

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

    # Filter PRs to only include those from scanned repos
    all_prs = [pr for pr in all_prs if pr["repository"]["name"] in repos]

    if not all_prs:
        print("✅ No open PRs found in scanned repositories")
        return

    # Count PRs by phase
    phase_counts = {"new": 0, "green": 0, "yellow": 0, "red": 0}
    for pr in all_prs:
        age = get_age_days(pr["createdAt"])
        phase_counts["new" if age == 0 else "green" if age <= 7 else "yellow" if age <= 30 else "red"] += 1

    summary = [
        f"# 🔍 Open Pull Requests - {org.title()} Organization\n",
        f"**Total:** {len(all_prs)} open PRs across {len({pr['repository']['name'] for pr in all_prs})}/{len(repos)} {filter_config['str']} repos",
        f"**By Phase:** 🆕 {phase_counts['new']} New | 🟢 {phase_counts['green']} ≤7d | 🟡 {phase_counts['yellow']} ≤30d | 🔴 {phase_counts['red']} >30d\n",
    ]

    for repo_name in sorted({pr["repository"]["name"] for pr in all_prs}):
        repo_prs = [pr for pr in all_prs if pr["repository"]["name"] == repo_name]
        summary.append(
            f"## 📦 [{repo_name}]({repos[repo_name]}) - {len(repo_prs)} open PR{'s' if len(repo_prs) > 1 else ''}"
        )

        for pr in repo_prs[:30]:
            emoji, age_str = get_phase_emoji(get_age_days(pr["createdAt"]))
            summary.append(f"- [#{pr['number']}]({pr['url']}) {pr['title']} {emoji} {age_str}")

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
                "number,title,url,files,mergeable,statusCheckRollup",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            continue

        merged = 0
        for pr in json.loads(result.stdout):
            paths = [f["path"] for f in pr["files"]]
            if not paths or not all(
                p.startswith(".github/workflows/") or p.endswith(("action.yml", "action.yaml")) for p in paths
            ):
                print("    ⏭️  Skipped (non-action files)")
                continue

            total_found += 1
            pr_link = pr.get("url", f"https://github.com/{org}/{repo_name}/pull/{pr['number']}")
            pr_ref = f"{org}/{repo_name}#{pr['number']}"
            print(f"  Found: {pr_link} - {pr['title']}")

            # Log status checks to help troubleshoot merge decisions
            rollup = pr.get("statusCheckRollup") or []
            checks = rollup if isinstance(rollup, list) else rollup.get("contexts", [])
            if checks:
                print("    ℹ️  Status checks:")
                for check in checks:
                    name = check.get("name") or check.get("context") or "unknown"
                    status = check.get("conclusion") or check.get("state") or ""
                    print(f"      - {name}: {status}")
            else:
                print("    ℹ️  No status checks found")

            if merged >= 1:
                print(f"    ⏭️  Skipped (already merged 1 PR in {repo_name})")
                total_skipped += 1
                continue

            if pr["mergeable"] != "MERGEABLE":
                print(f"    ❌ Skipped (not mergeable: {pr['mergeable']})")
                total_skipped += 1
                continue

            if failed := get_status_checks(pr.get("statusCheckRollup")):
                for check in failed:
                    name = check.get("name") or check.get("context") or "unknown"
                    status = check.get("conclusion") or check.get("state") or ""
                    print(f"    ❌ Failing check: {name} = {status}")
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

    if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a") as f:
            f.write("\n".join(summary))


if __name__ == "__main__":
    run()
