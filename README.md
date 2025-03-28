<a href="https://www.ultralytics.com/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320" alt="Ultralytics logo"></a>

# 🚀 Ultralytics Actions: Auto-Formatting for Python, Markdown, and Swift

Welcome to the [Ultralytics Actions](https://github.com/ultralytics/actions) repository, your go-to solution for maintaining consistent code quality across Ultralytics Python and Swift projects. This GitHub Action is designed to automate the formatting of Python, Markdown, and Swift files, ensuring adherence to our coding standards and enhancing project maintainability.

[![GitHub Actions Marketplace](https://img.shields.io/badge/Marketplace-Ultralytics_Actions-blue?style=flat&logo=github)](https://github.com/marketplace/actions/ultralytics-actions)
[![Ultralytics Actions](https://github.com/ultralytics/actions/actions/workflows/format.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/format.yml)
[![Ultralytics Discord](https://img.shields.io/discord/1089800235347353640?logo=discord&logoColor=white&label=Discord&color=blue)](https://discord.com/invite/ultralytics)
[![Ultralytics Forums](https://img.shields.io/discourse/users?server=https%3A%2F%2Fcommunity.ultralytics.com&logo=discourse&label=Forums&color=blue)](https://community.ultralytics.com/)
[![Ultralytics Reddit](https://img.shields.io/reddit/subreddit-subscribers/ultralytics?style=flat&logo=reddit&logoColor=white&label=Reddit&color=blue)](https://reddit.com/r/ultralytics)
[![PyPI version](https://badge.fury.io/py/ultralytics-actions.svg)](https://badge.fury.io/py/ultralytics-actions)
[![Downloads](https://static.pepy.tech/badge/ultralytics-actions)](https://www.pepy.tech/projects/ultralytics-actions)

## 📄 Actions Description

Ultralytics Actions automatically applies formats, updates, and enhancements using a suite of powerful tools:

- **Python Code:** Formatted using [Ruff](https://github.com/astral-sh/ruff), an extremely fast Python linter and formatter.
- **Markdown Files:** Styled with [Prettier](https://github.com/prettier/prettier) to ensure consistent documentation appearance.
- **Docstrings:** Cleaned and standardized using [docformatter](https://github.com/PyCQA/docformatter).
- **Swift Code:** Formatted with [`swift-format`](https://github.com/swiftlang/swift-format) to maintain a uniform coding style across Swift projects. _(Note: Requires the `macos-latest` runner.)_
- **Spell Check:** Common misspellings are caught using [codespell](https://github.com/codespell-project/codespell).
- **Broken Links Check:** Broken links in documentation and Markdown files are identified using [Lychee](https://github.com/lycheeverse/lychee).
- **PR Summary:** Concise Pull Request summaries are generated using [OpenAI](https://openai.com/) GPT-4o, improving clarity and review efficiency.
- **Auto-labeling:** Relevant labels are applied to issues and pull requests via [OpenAI](https://openai.com/) GPT-4o for intelligent categorization.

## 🛠️ How It Works

Ultralytics Actions triggers on various GitHub events to streamline workflows:

- **Push Events:** Automatically formats code when changes are pushed to the `main` branch.
- **Pull Requests:**
  - Ensures contributions meet formatting standards before merging.
  - Generates a concise summary of changes using GPT-4o.
  - Applies relevant labels using GPT-4o for intelligent categorization.
- **Issues:** Automatically applies relevant labels using GPT-4o when new issues are created.

These automated actions help maintain high code quality, improve documentation clarity, and streamline the review process by providing consistent formatting, informative summaries, and appropriate categorization.

## 🔧 Setting Up the Action

To integrate this action into your Ultralytics repository:

1.  **Create a Workflow File:** In your repository, create a YAML file under `.github/workflows/`, for example, `ultralytics-actions.yml`.

2.  **Add the Action:** Configure the Ultralytics Actions in your workflow file as shown below:

    ```yaml
    name: Ultralytics Actions

    on:
      issues:
        types: [opened]
      pull_request:
        branches: [main]
        types: [opened, closed]

    jobs:
      format:
        runs-on: ubuntu-latest # Use 'macos-latest' if 'swift: true'
        steps:
          - name: Run Ultralytics Formatting
            uses: ultralytics/actions@main
            with:
              token: ${{ secrets.GITHUB_TOKEN }} # Automatically generated, do not modify
              labels: true # Autolabel issues and PRs using GPT-4o (requires 'openai_api_key')
              python: true # Format Python code and docstrings with Ruff and docformatter
              prettier: true # Format YAML, JSON, Markdown, and CSS with Prettier
              swift: false # Format Swift code with swift-format (requires 'runs-on: macos-latest')
              spelling: true # Check spelling with codespell
              links: true # Check for broken links with Lychee
              summary: true # Generate PR summary with GPT-4o (requires 'openai_api_key')
              openai_api_key: ${{ secrets.OPENAI_API_KEY }} # Add your OpenAI API key as a repository secret
    ```

3.  **Customize:** Adjust the `runs-on` runner and the boolean flags (`labels`, `python`, `prettier`, `swift`, `spelling`, `links`, `summary`) based on your project's needs. Remember to add your `OPENAI_API_KEY` as a secret in your repository settings if you enable `labels` or `summary`.

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
