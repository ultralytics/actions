# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Generate GitHub organization reports."""

import json
import os
import subprocess
from datetime import datetime, timezone

from actions import failed_scheduled_actions

PASSING_CHECK_STATES = {"SUCCESS"}


def enabled(value):
    """Return whether a string environment-style value is enabled."""
    return str(value).lower() == "true"


def enabled_any(*values, default="true"):
    """Return the first explicitly set boolean value, otherwise the default."""
    return enabled(next((value for value in values if value not in {None, ""}), default))


def get_age_days(created_at):
    """Return the age in whole days from an ISO timestamp."""
    return (datetime.now(timezone.utc) - datetime.fromisoformat(created_at.replace("Z", "+00:00"))).days


def get_phase_emoji(age_days):
    """Return the age phase emoji and label."""
    if age_days == 0:
        return "🆕", "NEW"
    if age_days <= 7:
        return "🟢", f"{age_days} days"
    if age_days <= 30:
        return "🟡", f"{age_days} days"
    return "🔴", f"{age_days} days"


def get_status_checks(rollup):
    """Return status checks from a GitHub statusCheckRollup value."""
    return rollup if isinstance(rollup, list) else rollup.get("contexts", []) if isinstance(rollup, dict) else []


def get_unpassed_status_checks(rollup):
    """Return status checks that are not complete and passing."""
    checks = get_status_checks(rollup)
    return [
        check
        for check in checks
        if (check.get("conclusion") or check.get("state") or "").upper() not in PASSING_CHECK_STATES
    ]


def gh_json(args, check=True):
    """Run a GitHub CLI command and return parsed JSON output."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=check)
    return json.loads(result.stdout or "[]")


def collect_repos(org, visibility="public", repo_visibility="public"):
    """Collect non-archived repositories matching the requested visibility."""
    visibility_list = failed_scheduled_actions.parse_visibility(visibility, repo_visibility)
    filter_config = failed_scheduled_actions.get_repo_filter(visibility_list)
    repos = gh_json(["repo", "list", org, "--limit", "1000", "--json", "name,url,isArchived,visibility"])
    if len(visibility_list) == 1 and visibility_list[0] != "all":
        allowed = {visibility_list[0]}
    else:
        allowed = filter_config["filter"]
    return {
        repo["name"]: repo["url"]
        for repo in repos
        if not repo["isArchived"] and (not allowed or repo["visibility"].lower() in allowed)
    }, filter_config["str"]


def collect_open_prs(org, repos):
    """Collect open pull requests from the selected repositories."""
    prs = gh_json(
        [
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
        ]
    )
    return [pr for pr in prs if pr["repository"]["name"] in repos]


def format_pr_report(prs, repos, visibility, org="ultralytics"):
    """Format open pull requests as Markdown."""
    lines = [f"# 🔍 Open Pull Requests - {org.title()} Organization", ""]
    if not prs:
        lines.append("No open PRs found in scanned repositories.")
        return "\n".join(lines) + "\n"

    phase_counts = {"new": 0, "green": 0, "yellow": 0, "red": 0}
    for pr in prs:
        age = get_age_days(pr["createdAt"])
        phase_counts["new" if age == 0 else "green" if age <= 7 else "yellow" if age <= 30 else "red"] += 1

    repo_count = len({pr["repository"]["name"] for pr in prs})
    lines.extend(
        [
            f"**Total:** {len(prs)} open PRs across {repo_count}/{len(repos)} {visibility} repos",
            f"**By Phase:** 🆕 {phase_counts['new']} New | 🟢 {phase_counts['green']} ≤7d | "
            f"🟡 {phase_counts['yellow']} ≤30d | 🔴 {phase_counts['red']} >30d",
            "",
        ]
    )

    for repo_name in sorted({pr["repository"]["name"] for pr in prs}):
        repo_prs = [pr for pr in prs if pr["repository"]["name"] == repo_name]
        detail = f"{len(repo_prs)} open PR{'s' if len(repo_prs) > 1 else ''}"
        lines.append(f"{failed_scheduled_actions.format_repo_heading(repo_name, repos[repo_name])} - {detail}")
        for pr in repo_prs[:30]:
            emoji, age = get_phase_emoji(get_age_days(pr["createdAt"]))
            lines.append(f"- [#{pr['number']}]({pr['url']}) {pr['title']} {emoji} {age}")
        if len(repo_prs) > 30:
            lines.append(f"- ... {len(repo_prs) - 30} more PRs")
        lines.append("")
    return "\n".join(lines) + "\n"


def auto_merge_actions_prs(org, repos):
    """Auto-merge eligible GitHub Actions update pull requests."""
    print("\n🤖 Checking for GitHub Actions update PRs to auto-merge...")
    lines = ["# 🤖 Auto-Merge GitHub Actions Update PRs", ""]
    total_found = total_merged = total_skipped = 0
    approved_authors = ("app/dependabot", "UltralyticsAssistant")

    for repo_name in repos:
        prs = []
        for author in approved_authors:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    f"{org}/{repo_name}",
                    "--author",
                    author,
                    "--state",
                    "open",
                    "--json",
                    "number,title,url,files,mergeable,statusCheckRollup",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                prs.extend(json.loads(result.stdout or "[]"))

        merged = 0
        for pr in prs:
            title = pr.get("title", "").lower()
            if "bump" not in title or "/.github/workflows" not in title:
                continue

            total_found += 1
            pr_ref = f"{org}/{repo_name}#{pr['number']}"
            paths = [file["path"] for file in (pr.get("files") or [])]
            if not paths or any(
                not (path.startswith(".github/workflows/") or path.endswith(("action.yml", "action.yaml")))
                for path in paths
            ):
                print("    ⏭️  Skipped (mixed or non-action files)")
                lines.append(f"- ❌ {pr_ref}: mixed or non-action files")
                total_skipped += 1
                continue

            pr_url = pr.get("url") or f"https://github.com/{org}/{repo_name}/pull/{pr['number']}"
            print(f"  Found: {pr_url} - {pr['title']}")

            checks = get_status_checks(pr.get("statusCheckRollup"))
            if checks:
                print("    ℹ️  Status checks:")
                for check in checks:
                    name = check.get("name") or check.get("context") or "unknown"
                    status = check.get("conclusion") or check.get("state") or ""
                    print(f"      - {name}: {status}")
            else:
                print("    ❌ Skipped (no status checks found)")
                lines.append(f"- ❌ {pr_ref}: no status checks found")
                total_skipped += 1
                continue

            if merged >= 1:
                print(f"    ⏭️  Skipped (already merged 1 PR in {repo_name})")
                total_skipped += 1
                continue

            mergeable = pr.get("mergeable", "UNKNOWN")
            if mergeable == "CONFLICTING":
                print("    ❌ Skipped (merge conflicts)")
                lines.append(f"- ❌ {pr_ref}: merge conflicts")
                total_skipped += 1
                continue

            if unpassed := get_unpassed_status_checks(pr.get("statusCheckRollup")):
                names = ", ".join(check.get("name") or check.get("context") or "?" for check in unpassed)
                print(f"    ❌ Skipped (checks not passing: {names})")
                lines.append(f"- ❌ {pr_ref}: checks not passing ({names})")
                total_skipped += 1
                continue

            print(f"    🔀 Merging (mergeable={mergeable})...")
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "merge",
                    str(pr["number"]),
                    "--repo",
                    f"{org}/{repo_name}",
                    "--squash",
                    "--admin",
                    "--delete-branch",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"    ✅ Merged {pr_ref}")
                lines.append(f"- ✅ Merged {pr_ref}")
                total_merged += 1
                merged += 1
            else:
                error = result.stderr.strip()
                print(f"    ❌ Merge failed: {error}")
                lines.append(f"- ❌ {pr_ref}: {error[:80]}")
                total_skipped += 1

    lines.append(f"\n**Summary:** Found {total_found} | Merged {total_merged} | Skipped {total_skipped}")
    print(f"\n📊 Auto-Merge Summary: Found {total_found} | Merged {total_merged} | Skipped {total_skipped}")
    return "\n".join(lines) + "\n"


def run_pr_report():
    """Write open PR and optional auto-merge reports to stdout and the GitHub step summary."""
    org = os.getenv("ORG", "ultralytics")
    repos, visibility = collect_repos(org, os.getenv("VISIBILITY", "public"), os.getenv("REPO_VISIBILITY", "public"))
    print(f"🔍 Scanning {visibility} repositories in {org} organization...")
    report = format_pr_report(collect_open_prs(org, repos) if repos else [], repos, visibility, org)

    if enabled(os.getenv("AUTO_MERGE_ACTIONS_PRS", "true")):
        report += "\n" + auto_merge_actions_prs(org, repos)
    else:
        report += "\n# 🤖 Auto-Merge GitHub Actions Update PRs\n\nAuto-merge disabled for this run.\n"

    print(report)
    if summary_file := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a") as f:
            f.write(report)


def run():
    """Run enabled GitHub report sections."""
    if enabled(os.getenv("REPORT_PRS", "true")):
        run_pr_report()
    if enabled_any(os.getenv("REPORT_FAILED_ACTIONS"), os.getenv("REPORT_FAILED_SCHEDULED_ACTIONS")):
        failed_scheduled_actions.run()


if __name__ == "__main__":
    run()
