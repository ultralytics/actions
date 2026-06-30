# GitHub Report Action

Summarize failed default-branch GitHub Actions across organization repositories.

## Usage

```yaml
name: GitHub Daily Report
on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * *"

permissions:
  contents: read
  actions: read

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
```

## Inputs

| Input                      | Description                                                                   | Required | Default       |
| -------------------------- | ----------------------------------------------------------------------------- | -------- | ------------- |
| `token`                    | GitHub token with access to organization repositories                         | Yes      | -             |
| `org`                      | GitHub organization name                                                      | No       | `ultralytics` |
| `visibility`               | Repository visibility: `public`, `private`, `internal`, `all`                 | No       | `public`      |
| `failed_actions`           | Include failed default-branch Actions summary                                 | No       | `true`        |
| `failed_scheduled_actions` | Deprecated alias for `failed_actions`                                         | No       | -             |
| `max_run_pages`            | Pages of workflow runs to inspect per repository                              | No       | `3`           |
| `days`                     | Days of workflow history to include                                           | No       | `1`           |

## Output

The action writes a GitHub step summary with:

- Latest failed workflow runs on each repository's default branch, grouped by event
