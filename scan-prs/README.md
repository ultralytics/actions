# Scan PRs Action

List open PRs across an organization and auto-merge eligible GitHub Actions update PRs.

## Features

- **PR Overview**: Lists all open PRs with age-based categorization (New, Green ≤7d, Yellow ≤30d, Red >30d)
- **Auto-merge**: Automatically merges Dependabot and UltralyticsAssistant PRs that update GitHub Actions when no checks have failed
- **Console Logging**: Detailed output showing which PRs were found, merged, or skipped with reasons

## Usage

```yaml
name: Scan PRs
on:
  workflow_dispatch:
  schedule:
    - cron: "0 3 * * *" # daily at 03:00 UTC

permissions:
  contents: write
  pull-requests: write

jobs:
  scan-prs:
    runs-on: ubuntu-latest
    steps:
      - uses: ultralytics/actions/scan-prs@main
        with:
          token: ${{ secrets._GITHUB_TOKEN }} # PAT with access to org repos (default GITHUB_TOKEN is limited to the current repo)
          org: ultralytics # Optional: defaults to ultralytics
          visibility: private,internal # Optional: public, private, internal, all, or comma-separated
```

## Inputs

| Input        | Description                                                                                                               | Required | Default       |
| ------------ | ------------------------------------------------------------------------------------------------------------------------- | -------- | ------------- |
| `token`      | GitHub token with admin permissions for merging                                                                           | Yes      | -             |
| `org`        | GitHub organization name                                                                                                  | No       | `ultralytics` |
| `visibility` | Repository visibility to scan: `public`, `private`, `internal`, `all`, or comma-separated list (e.g., `private,internal`) | No       | `public`      |

**Security Note:** If the calling repository is public, scanning is automatically restricted to public repos only, even if non-public visibilities are specified.

## Auto-merge Criteria

GitHub Actions update PRs are automatically merged if they meet ALL criteria:

1. Authored by Dependabot or UltralyticsAssistant
2. Title contains `bump` and `/.github/workflows` (a GitHub Actions version bump)
3. Update at least one GitHub Actions file (in `.github/workflows/`, or an `action.yml`/`action.yaml`)
4. PR is mergeable (no conflicts)
5. No status checks in a failed state (`FAILURE`, `ERROR`, `CANCELLED`, `TIMED_OUT`, `ACTION_REQUIRED`, `STARTUP_FAILURE`); pending or absent checks do not block merging
6. Maximum 1 PR merged per repository per run

## Output

The action generates a GitHub step summary with:

- Total PR count across all repos
- PR breakdown by phase (New, Green, Yellow, Red)
- Detailed list of PRs per repository
- Summary of GitHub Actions update PRs found, merged, and skipped
