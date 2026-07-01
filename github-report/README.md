# GitHub Report Action

Summarize open PRs and failed default-branch GitHub Actions across organization repositories.

## Usage

```yaml
name: GitHub Daily Report
on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * *"

permissions:
  contents: write
  actions: read
  pull-requests: write

jobs:
  github-report:
    runs-on: ubuntu-latest
    steps:
      - uses: ultralytics/actions/github-report@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          org: ultralytics
          visibility: private,internal
          days: 1
          auto_merge_actions_prs: true
```

## Inputs

| Input                      | Description                                                   | Required | Default       |
| -------------------------- | ------------------------------------------------------------- | -------- | ------------- |
| `token`                    | GitHub token with access to organization repositories         | Yes      | -             |
| `org`                      | GitHub organization name                                      | No       | `ultralytics` |
| `visibility`               | Repository visibility: `public`, `private`, `internal`, `all` | No       | `public`      |
| `prs`                      | Include open PR summary                                       | No       | `true`        |
| `failed_actions`           | Include failed default-branch Actions summary                 | No       | `true`        |
| `failed_scheduled_actions` | Deprecated alias for `failed_actions`                         | No       | -             |
| `auto_merge_actions_prs`   | Auto-merge eligible GitHub Actions update PRs                 | No       | `true`        |
| `max_run_pages`            | Pages of workflow runs to inspect per repository              | No       | `3`           |
| `days`                     | Days of workflow history to include                           | No       | `1`           |

## Output

The action writes a GitHub step summary with:

- Latest failed workflow runs on each repository's default branch, grouped by event
- Open PRs by repository with age-based status
- Eligible GitHub Actions update PRs merged or skipped with reasons
