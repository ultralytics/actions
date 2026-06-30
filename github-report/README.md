# GitHub Report Action

Summarize open pull requests and failed scheduled GitHub Actions across organization repositories.

## Usage

```yaml
name: GitHub Daily Report
on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * *"

permissions:
  contents: read
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
```

## Inputs

| Input                      | Description                                                                    | Required | Default       |
| -------------------------- | ------------------------------------------------------------------------------ | -------- | ------------- |
| `token`                    | GitHub token with access to scanned repositories                               | Yes      | -             |
| `org`                      | GitHub organization name                                                       | No       | `ultralytics` |
| `visibility`               | Repository visibility for PR scanning: `public`, `private`, `internal`, `all` | No       | `public`      |
| `prs`                      | Include open PR summary                                                        | No       | `true`        |
| `failed_scheduled_actions` | Include failed scheduled Actions summary                                       | No       | `true`        |
| `auto_merge_actions_prs`   | Auto-merge eligible GitHub Actions update PRs in the PR section                | No       | `true`        |
| `max_run_pages`            | Pages of scheduled workflow runs to inspect per repository                     | No       | `3`           |

## Output

The action writes a GitHub step summary with:

- Open PR totals and age buckets
- Eligible GitHub Actions update PR merge results
- Latest failed scheduled workflow runs on each repository's default branch
