<a href="https://www.ultralytics.com/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320" alt="Ultralytics logo"></a>

[English](README.md) | [简体中文](README.zh-CN.md)

# 🚀 Ultralytics Actions

欢迎使用 [Ultralytics Actions](https://github.com/ultralytics/actions) - 这是一组 GitHub Actions，用于在 Ultralytics 项目中自动化代码质量、PR 管理和 CI/CD 工作流。

[![GitHub Actions Marketplace](https://img.shields.io/badge/Marketplace-Ultralytics_Actions-blue?style=flat&logo=github)](https://github.com/marketplace/actions/ultralytics-actions)

[![Actions CI](https://github.com/ultralytics/actions/actions/workflows/ci.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/ci.yml)
[![Ultralytics Actions](https://github.com/ultralytics/actions/actions/workflows/format.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/format.yml)
[![GitHub Report](https://github.com/ultralytics/actions/actions/workflows/github_report.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/github_report.yml)
[![codecov](https://codecov.io/github/ultralytics/actions/branch/main/graph/badge.svg)](https://app.codecov.io/github/ultralytics/actions)

[![Ultralytics Discord](https://img.shields.io/discord/1089800235347353640?logo=discord&logoColor=white&label=Discord&color=blue)](https://discord.com/invite/ultralytics)
[![Ultralytics Forums](https://img.shields.io/discourse/users?server=https%3A%2F%2Fcommunity.ultralytics.com&logo=discourse&label=Forums&color=blue)](https://community.ultralytics.com/)
[![Ultralytics Reddit](https://img.shields.io/reddit/subreddit-subscribers/ultralytics?style=flat&logo=reddit&logoColor=white&label=Reddit&color=blue)](https://reddit.com/r/ultralytics)

## 📦 仓库内容

本仓库提供三个主要组成部分：

1. **[Ultralytics Actions](#ultralytics-actions-主-action)** - 用于 AI 代码格式化、PR 摘要和自动标签的主 GitHub Action
2. **[独立 Actions](#独立-actions)** - 可在常见 CI/CD 任务中复用的 composite actions
3. **[Python 包](#python-包)** - 可编程使用的 `ultralytics-actions` 包

## Ultralytics Actions 主 Action

面向 Python、JavaScript/TypeScript、Swift、Dart 和网页/文档文件的 AI 驱动格式化、标签和 PR 摘要工具。

### 📄 功能

- **Python 代码：** 使用极快的 Python linter 和 formatter [Ruff](https://github.com/astral-sh/ruff) 格式化
- **Python Docstrings：** 使用 Ultralytics Python docstring formatter 强制 Google 风格格式（可选）
- **JavaScript/TypeScript：** 使用极快的 JS、TS、JSX、TSX 和 JSON formatter [Biome](https://biomejs.dev/) 格式化（可选，通过 `biome.json` 或 `biome.jsonc` 自动检测）
- **Web 和文档文件：** 使用 [Prettier](https://github.com/prettier/prettier) 格式化 JS、TS、CSS、HTML、JSON、YAML、Markdown 和 shell 脚本
- **Swift 代码：** 使用 [`swift-format`](https://github.com/swiftlang/swift-format) 格式化（需要 `macos-latest` runner）
- **Dart 代码：** 使用 [`dart format`](https://dart.dev/tools/dart-format) 格式化 Dart 和 Flutter 项目
- **拼写检查：** 使用 [codespell](https://github.com/codespell-project/codespell) 捕获常见拼写错误
- **断链检查：** 使用 [Lychee](https://github.com/lycheeverse/lychee) 识别无效链接
- **PR 摘要：** 使用 AI 生成简洁的 Pull Request 摘要
- **PR Review：** AI 代码审查可识别关键 bug、安全问题和质量问题，并给出修复建议
- **自动标签：** 使用 AI 为 issues、PRs 和 discussions 应用相关标签

### 🤖 支持的 AI 提供商

可选择 [OpenAI](https://developers.openai.com/) 或 [Anthropic](https://www.anthropic.com/) 启用 AI 功能：

| 提供商    | 默认模型            | API Key             |
| --------- | ------------------- | ------------------- |
| OpenAI    | `gpt-5.5`           | `openai_api_key`    |
| Anthropic | `claude-sonnet-4-6` | `anthropic_api_key` |

模型会根据提供的 API key 自动检测。可通过 `model` 输入覆盖默认模型，也可使用 `review_model` 仅覆盖 PR review 模型。

### 🛠️ 工作方式

通过 GitHub 事件触发并简化工作流：

- **Pull Requests：** 确保格式标准、生成摘要、提供 AI review，并应用标签
- **Issues：** 使用 AI 自动应用相关标签
- **Discussions：** 使用 AI 自动应用相关标签

### 🔧 设置

创建 `.github/workflows/ultralytics-actions.yml`：

```yaml
# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# Ultralytics Actions https://github.com/ultralytics/actions
# This workflow formats code and documentation in PRs to Ultralytics standards

name: Ultralytics Actions

on:
  issues:
    types: [opened]
  discussion:
    types: [created]
  pull_request:
    branches: [main]
    types: [opened, closed, synchronize, review_requested]

permissions:
  contents: write # Modify code in PRs
  pull-requests: write # Add comments and labels to PRs
  issues: write # Add comments and labels to issues
  discussions: write # Add labels to discussions

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
          # python-version: "3.14" # Optional: set up a specific Python version (default: runner Python)
          python_docstrings: true # Format Python docstrings (default: true)
          biome: true # Format JS/TS with Biome (auto-detected via biome.json or biome.jsonc)
          prettier: true # Format YAML, JSON, Markdown, CSS
          swift: false # Format Swift (requires macos-latest)
          dart: false # Format Dart/Flutter
          spelling: true # Check spelling with codespell
          links: true # Check broken links with Lychee
          summary: true # Generate AI-powered PR summaries
          # AI API keys - provide OpenAI OR Anthropic (model auto-detected from key)
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          # anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          # model: gpt-5.5  # Optional: set model explicitly
          # review_model: claude-opus-4-7  # Optional: override PR review model
          brave_api_key: ${{ secrets.BRAVE_API_KEY }} # Used for broken link resolution
```

## 独立 Actions

这些可复用 composite actions 可在工作流中独立使用。

### 1. Retry Action

使用指数退避和 jitter 重试失败命令。

```yaml
- uses: ultralytics/actions/retry@main
  with:
    run: npm install
    retries: 3
    timeout_minutes: 5
```

[**📖 完整文档 →**](retry/README.md)

### 2. Cleanup Disk Action

通过删除不必要的软件包和文件释放 GitHub runners 的磁盘空间。

```yaml
- uses: ultralytics/actions/cleanup-disk@main
```

[**📖 完整文档 →**](cleanup-disk/README.md)

### 3. GitHub Report Action

汇总组织仓库中的 open PR 以及默认分支上失败的 GitHub Actions。

```yaml
- uses: ultralytics/actions/github-report@main
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    org: ultralytics # Optional: defaults to ultralytics
    visibility: all # Optional: public, private, internal, all, or comma-separated
    auto_merge_actions_prs: true # Optional: auto-merge eligible GitHub Actions update PRs
```

[**📖 完整文档 →**](github-report/README.md)

### 4. Dependabot Action

使用缓存的 release 解析，批量更新组织仓库中的 GitHub Actions 版本。

```yaml
- uses: ultralytics/actions/dependabot@main
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
```

[**📖 完整文档 →**](dependabot/README.md)

## Python 包

在 [**Python>=3.8**](https://www.python.org/) 环境中安装 `ultralytics-actions` 包及其全部[依赖项](https://github.com/ultralytics/actions/blob/main/pyproject.toml)，以便通过代码使用 action 工具。

[![PyPI - Version](https://img.shields.io/pypi/v/ultralytics-actions?logo=pypi&logoColor=white)](https://pypi.org/project/ultralytics-actions/) [![Ultralytics Downloads](https://static.pepy.tech/badge/ultralytics-actions)](https://clickpy.clickhouse.com/dashboard/ultralytics-actions) [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ultralytics-actions?logo=python&logoColor=gold)](https://pypi.org/project/ultralytics-actions/)

```bash
uv pip install ultralytics-actions
```

**可用模块：**

- `actions.review_pr` - AI 驱动的 PR review
- `actions.summarize_pr` - 生成 PR 摘要
- `actions.github_report` - 生成 GitHub 组织报告
- `actions.first_interaction` - 为新贡献者生成欢迎消息
- 更多模块见 `actions/` 目录

## 💡 贡献

Ultralytics 依靠社区协作不断发展，我们非常重视您的贡献！请查看[贡献指南](https://docs.ultralytics.com/help/contributing)了解如何参与。也欢迎通过我们的[调查问卷](https://www.ultralytics.com/survey?utm_source=github&utm_medium=social&utm_campaign=Survey)分享反馈。衷心感谢 🙏 每一位贡献者！

[![Ultralytics open-source contributors](https://raw.githubusercontent.com/ultralytics/assets/main/im/image-contributors.png)](https://github.com/ultralytics/ultralytics/graphs/contributors)

## 📄 许可证

Ultralytics 提供两种许可选项：

- **AGPL-3.0 许可证：** 经 [OSI 批准](https://opensource.org/license/agpl-3.0)的开源许可证，适合重视开放协作的学生、研究人员和爱好者。详情请参阅 [LICENSE](https://github.com/ultralytics/actions/blob/main/LICENSE) 文件。
- **企业许可证：** 面向商业用途，可将 Ultralytics 软件和 AI 模型集成到商业产品中，而不受 AGPL-3.0 开源要求限制。如需企业方案，请联系 [Ultralytics Licensing](https://www.ultralytics.com/license)。

## 📫 联系

如需报告 Ultralytics Actions 相关 bug 或提出功能建议，请通过 [GitHub Issues](https://github.com/ultralytics/actions/issues) 提交。欢迎加入我们的 [Discord](https://discord.com/invite/ultralytics) 社区参与讨论并获取支持！

<br>
<div align="center">
  <a href="https://github.com/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-github.png" width="3%" alt="Ultralytics GitHub"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.linkedin.com/company/ultralytics/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-linkedin.png" width="3%" alt="Ultralytics LinkedIn"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://twitter.com/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-twitter.png" width="3%" alt="Ultralytics Twitter"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.youtube.com/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-youtube.png" width="3%" alt="Ultralytics YouTube"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.tiktok.com/@ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-tiktok.png" width="3%" alt="Ultralytics TikTok"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://ultralytics.com/bilibili"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-bilibili.png" width="3%" alt="Ultralytics BiliBili"></a>
  <img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://discord.com/invite/ultralytics"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/social/logo-social-discord.png" width="3%" alt="Ultralytics Discord"></a>
</div>
