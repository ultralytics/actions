<a href="https://www.ultralytics.com/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320" alt="Ultralytics logo"></a>

# 🚀 Ultralytics Actions

Welcome to [Ultralytics Actions](https://github.com/ultralytics/actions) - a collection of GitHub Actions and Python tools for automating code quality, PR management, and CI/CD workflows across Ultralytics projects.

[![GitHub Actions Marketplace](https://img.shields.io/badge/Marketplace-Ultralytics_Actions-blue?style=flat&logo=github)](https://github.com/marketplace/actions/ultralytics-actions)

[![Actions CI](https://github.com/ultralytics/actions/actions/workflows/ci.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/ci.yml)
[![Ultralytics Actions](https://github.com/ultralytics/actions/actions/workflows/format.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/format.yml)
[![Scan PRs](https://github.com/ultralytics/actions/actions/workflows/scan-prs.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/scan-prs.yml)
[![codecov](https://codecov.io/github/ultralytics/actions/graph/badge.svg?token=DoizJ1WS6j)](https://codecov.io/github/ultralytics/actions)

[![Ultralytics Discord](https://img.shields.io/discord/1089800235347353640?logo=discord&logoColor=white&label=Discord&color=blue)](https://discord.com/invite/ultralytics)
[![Ultralytics Forums](https://img.shields.io/discourse/users?server=https%3A%2F%2Fcommunity.ultralytics.com&logo=discourse&label=Forums&color=blue)](https://community.ultralytics.com/)
[![Ultralytics Reddit](https://img.shields.io/reddit/subreddit-subscribers/ultralytics?style=flat&logo=reddit&logoColor=white&label=Reddit&color=blue)](https://reddit.com/r/ultralytics)

## 📦 Repository Contents

This repository provides three main components:

1. **[Ultralytics Actions](#ultralytics-actions-main-action)** - Main GitHub Action for AI-powered code formatting, PR summaries, and auto-labeling
2. **[Standalone Actions](#standalone-actions)** - Reusable composite actions for common CI/CD tasks
3. **[Python Package](#python-package)** - `ultralytics-actions` package for programmatic use

## Ultralytics Actions (Main Action)

AI-powered formatting, labeling, and PR summaries for Python, Swift, and Markdown files.

### 📄 Features

- **Python Code:** Formatted using [Ruff](https://github.com/astral-sh/ruff), an extremely fast Python linter and formatter
- **Python Docstrings:** Google-style formatting enforced with Ultralytics Python docstring formatter (optional)
- **JavaScript/TypeScript:** Formatted with [Biome](https://biomejs.dev/), an extremely fast formatter for JS, TS, JSX, TSX, and JSON (optional, auto-detected via `biome.json`)
- **Markdown Files:** Styled with [Prettier](https://github.com/prettier/prettier) to ensure consistent documentation appearance
- **Swift Code:** Formatted with [`swift-format`](https://github.com/swiftlang/swift-format) _(requires `macos-latest` runner)_
- **Spell Check:** Common misspellings caught using [codespell](https://github.com/codespell-project/codespell)
- **Broken Links Check:** Broken links identified using [Lychee](https://github.com/lycheeverse/lychee)
- **PR Summary:** Concise Pull Request summaries generated using [OpenAI](https://openai.com/) GPT-5
- **PR Review:** AI-powered code reviews identify critical bugs, security issues, and quality concerns with suggested fixes
- **Auto-labeling:** Applies relevant labels to issues and PRs via [OpenAI](https://openai.com/) GPT-5

### 🛠️ How It Works

Triggers on GitHub events to streamline workflows:

- **Push Events:** Automatically formats code when changes are pushed to `main`
- **Pull Requests:** Ensures formatting standards, generates summaries, provides AI reviews, and applies labels
- **Issues:** Automatically applies relevant labels using GPT-5

### 🔧 Setup

Create `.github/workflows/ultralytics-actions.yml`:

```yaml
# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# Ultralytics Actions https://github.com/ultralytics/actions
# This workflow formats code and documentation in PRs to Ultralytics standards

name: Ultralytics Actions

on:
  issues:
    types: [opened]
  pull_request:
    branches: [main]
    types: [opened, closed, synchronize, review_requested]

permissions:
  contents: write # Modify code in PRs
  pull-requests: write # Add comments and labels to PRs
  issues: write # Add comments and labels to issues

jobs:
  actions:
    runs-on: ubuntu-latest
    steps:
      - name: Run Ultralytics Actions
        uses: ultralytics/actions@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }} # Auto-generated token
          labels: true # Auto-label issues/PRs using AI
          python: true # Format Python with Ruff
          python_docstrings: false # Format Python docstrings (default: false)
          biome: true # Format JS/TS with Biome (auto-detected via biome.json)
          prettier: true # Format YAML, JSON, Markdown, CSS
          swift: false # Format Swift (requires macos-latest)
          dart: false # Format Dart/Flutter
          spelling: true # Check spelling with codespell
          links: true # Check broken links with Lychee
          summary: true # Generate AI-powered PR summaries
          openai_api_key: ${{ secrets.OPENAI_API_KEY }} # Powers PR summaries, labels and reviews
          brave_api_key: ${{ secrets.BRAVE_API_KEY }} # Used for broken link resolution
```

## Standalone Actions

Reusable composite actions for common CI/CD tasks. Each can be used independently in your workflows.

### 1. Retry Action

Retry failed commands with exponential backoff.

```yaml
- uses: ultralytics/actions/retry@main
  with:
    command: npm install
    max_attempts: 3
    timeout_minutes: 5
```

[**📖 Full Documentation →**](retry/README.md)

### 2. Cleanup Disk Action

Free up disk space on GitHub runners by removing unnecessary packages and files.

```yaml
- uses: ultralytics/actions/cleanup-disk@main
```

[**📖 Full Documentation →**](cleanup-disk/README.md)

### 3. Scan PRs Action

List open PRs across an organization and auto-merge eligible Dependabot PRs.

```yaml
- uses: ultralytics/actions/scan-prs@main
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    org: ultralytics # Optional: defaults to ultralytics
    visibility: private,internal # Optional: public, private, internal, all, or comma-separated
```

[**📖 Full Documentation →**](scan-prs/README.md)

## Python Package

Install `ultralytics-actions` for programmatic access to action utilities.

[![PyPI - Version](https://img.shields.io/pypi/v/ultralytics-actions?logo=pypi&logoColor=white)](https://pypi.org/project/ultralytics-actions/)
[![Ultralytics Downloads](https://static.pepy.tech/badge/ultralytics-actions)](https://clickpy.clickhouse.com/dashboard/ultralytics-actions)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ultralytics-actions?logo=python&logoColor=gold)](https://pypi.org/project/ultralytics-actions/)

```bash
pip install ultralytics-actions
```

**Available Modules:**

- `actions.review_pr` - AI-powered PR review
- `actions.summarize_pr` - Generate PR summaries
- `actions.scan_prs` - Scan and manage organization PRs
- `actions.first_interaction` - Welcome message for new contributors
- And more in `actions/` directory

## 💡 Contribute

Ultralytics thrives on community collaboration, and we deeply value your contributions! Please see our [Contributing Guide](https://docs.ultralytics.com/help/contributing/) for details on how you can get involved. We also encourage you to share your feedback through our [Survey](https://www.ultralytics.com/survey?utm_source=github&utm_medium=social&utm_campaign=Survey). A huge thank you 🙏 to all our contributors!

[![Ultralytics open-source contributors](https://raw.githubusercontent.com/ultralytics/assets/main/im/image-contributors.png)](https://github.com/ultralytics/ultralytics/graphs/contributors)

## 📄 License

Ultralytics offers two licensing options:

- **AGPL-3.0 License**: An [OSI-approved](https://opensource.org/license/agpl-v3) open-source license ideal for students, researchers, and enthusiasts who value open collaboration. See the [LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) file for details.
- **Enterprise License**: Designed for commercial use, this license allows integrating Ultralytics software and AI models into commercial products without AGPL-3.0's open-source requirements. For enterprise solutions, contact [Ultralytics Licensing](https://www.ultralytics.com/license).

## 📫 Contact

For bug reports or feature suggestions related to Ultralytics Actions, please submit an issue via [GitHub Issues](https://github.com/ultralytics/actions/issues). Join our [Discord](https://discord.com/invite/ultralytics) community for discussions and support!

<br>
<div align="center">
  <a href="https://github.com/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-github.png" width="3%" alt="Ultralytics GitHub"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.linkedin.com/company/ultralytics/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-linkedin.png" width="3%" alt="Ultralytics LinkedIn"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://twitter.com/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-twitter.png" width="3%" alt="Ultralytics Twitter"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://youtube.com/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-youtube.png" width="3%" alt="Ultralytics YouTube"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.tiktok.com/@ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-tiktok.png" width="3%" alt="Ultralytics TikTok"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://ultralytics.com/bilibili"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-bilibili.png" width="3%" alt="Ultralytics BiliBili"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://discord.com/invite/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-discord.png" width="3%" alt="Ultralytics Discord"></a>
</div>
