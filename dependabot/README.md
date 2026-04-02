# Dependabot Action

Update GitHub Actions versions across organization repos with cached version resolution. Designed for private/internal repos where GitHub's built-in Dependabot is not available.

## Usage

```yaml
name: Dependabot
on:
  workflow_dispatch:
  schedule:
    - cron: "0 5 * * 1" # weekly on Monday at 05:00 UTC

jobs:
  dependabot:
    runs-on: ubuntu-latest
    steps:
      - uses: ultralytics/actions/dependabot@main
        with:
          token: ${{ secrets._GITHUB_TOKEN }}
```

## Inputs

| Input      | Description                                                                      | Required | Default       |
| ---------- | -------------------------------------------------------------------------------- | -------- | ------------- |
| `token`    | GitHub token with `contents:write`, `pull-requests:write`, and `workflow` scopes | Yes      | -             |
| `org`      | GitHub organization name                                                         | No       | `ultralytics` |
| `public`   | Scan public repositories                                                         | No       | `true`        |
| `private`  | Scan private repositories                                                        | No       | `true`        |
| `internal` | Scan internal repositories                                                       | No       | `true`        |

## How It Works

1. Lists all active repos in the org (filtered by visibility)
2. Fetches workflow files (`.github/workflows/*.yml` and `action.yml`) from each repo
3. Parses `uses:` lines and resolves the latest release for each action
4. Creates one PR per outdated action per repo, updating all files that reference it
5. Skips PRs that already exist (matches by title)

## Version Handling

| Format       | Example               | Behavior                                         |
| ------------ | --------------------- | ------------------------------------------------ |
| Branch       | `@main`               | Skipped                                          |
| Major tag    | `@v7`                 | Updated to `@v8` only if the upstream `v8` tag exists |
| Specific tag | `@v2.8.0`             | Updated to a newer release tag                   |
| SHA pinned   | `@abc123... # v7.0.0` | SHA + comment updated to latest                  |

## Caching

Action versions are resolved once and reused across all repos. For an org with 60 repos using 15 common actions, this saves ~885 API calls per run.
