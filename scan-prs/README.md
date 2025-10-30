# Scan PRs Action

List open PRs across an organization and auto-merge eligible Dependabot PRs.

## Features

- **PR Overview**: Lists all open PRs with age-based categorization (New, Green ≤7d, Yellow ≤30d, Red >30d)
- **Auto-merge**: Automatically merges Dependabot PRs that update GitHub Actions workflows when all checks pass
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
          token: ${{ secrets.GITHUB_TOKEN }}
```

## Inputs

| Input        | Description                                                              | Required | Default       |
| ------------ | ------------------------------------------------------------------------ | -------- | ------------- |
| `token`      | GitHub token with admin permissions for merging                          | Yes      | -             |
| `org`        | GitHub organization name                                                 | No       | `ultralytics` |
| `visibility` | Repository visibility to scan: `public`, `private`, `internal`, or `all` | No       | `public`      |

**Security Note:** If the calling repository is public, scanning is automatically restricted to public repos only, even if a different visibility is specified.

## Auto-merge Criteria

Dependabot PRs are automatically merged if they meet ALL criteria:

1. Update files in `.github/workflows/` only
2. PR is mergeable (no conflicts)
3. All status checks passed (SUCCESS, SKIPPED, or NEUTRAL)
4. Maximum 1 PR merged per repository per run

## Output

The action generates a GitHub step summary with:

- Total PR count across all repos
- PR breakdown by phase (New, Green, Yellow, Red)
- Detailed list of PRs per repository
- Summary of Dependabot PRs found, merged, and skipped
