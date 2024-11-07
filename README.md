<a href="https://www.ultralytics.com/" target="_blank"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320" alt="Ultralytics logo"></a>

# 🚀 Ultralytics Actions: Auto-Formatting for Python, Markdown, and Swift

Welcome to the [Ultralytics Actions](https://github.com/ultralytics/actions) repository, your go-to solution for maintaining consistent code quality across Ultralytics Python and Swift projects. This GitHub Action is designed to automate the formatting of Python, Markdown, and Swift files, ensuring adherence to our coding standards.

[![GitHub Actions Marketplace](https://img.shields.io/badge/Marketplace-Ultralytics_Actions-blue?style=flat&logo=github)](https://github.com/marketplace/actions/ultralytics-actions) [![Ultralytics Actions](https://github.com/ultralytics/actions/actions/workflows/format.yml/badge.svg)](https://github.com/ultralytics/actions/actions/workflows/format.yml) <a href="https://discord.com/invite/ultralytics"><img alt="Discord" src="https://img.shields.io/discord/1089800235347353640?logo=discord&logoColor=white&label=Discord&color=blue"></a> <a href="https://community.ultralytics.com/"><img alt="Ultralytics Forums" src="https://img.shields.io/discourse/users?server=https%3A%2F%2Fcommunity.ultralytics.com&logo=discourse&label=Forums&color=blue"></a> <a href="https://reddit.com/r/ultralytics"><img alt="Ultralytics Reddit" src="https://img.shields.io/reddit/subreddit-subscribers/ultralytics?style=flat&logo=reddit&logoColor=white&label=Reddit&color=blue"></a>

[![PyPI version](https://badge.fury.io/py/ultralytics-actions.svg)](https://badge.fury.io/py/ultralytics-actions) [![Downloads](https://static.pepy.tech/badge/ultralytics-actions)](https://www.pepy.tech/projects/ultralytics-actions)

## 📄 Actions Description

Ultralytics Actions automatically applies formats, updates, and enhancements:

- **Python Code:** Using [Ruff](https://github.com/astral-sh/ruff), a fast Python auto-formatter.
- **Markdown Files:** With [Prettier](https://github.com/prettier/prettier), ensuring a consistent style in documentation.
- **Docstrings:** Utilizing [docformatter](https://github.com/PyCQA/docformatter) for clean and standardized documentation comments.
- **Swift Code:** Formatting Swift files using `swift-format` to ensure consistent coding style across Swift projects. _(Requires `macos-latest` to run correctly.)_
- **Spell Check:** Employing [codespell](https://github.com/codespell-project/codespell) for catching common misspellings.
- **Broken Links Check:** Implementing [Lychee](https://github.com/lycheeverse/lychee) to report broken links in docs and markdown files.
- **PR Summary:** Generating concise [OpenAI](https://openai.com/) GPT4o-powered PR summaries, enhancing PR clarity.
- **Auto-labeling:** Applying relevant labels to issues and pull requests using [OpenAI](https://openai.com/) GPT-4o for intelligent categorization.

## 🛠 How It Works

Ultralytics Actions triggers on various GitHub events:

- **Push Events:** Automatically formats code when changes are pushed to the `main` branch.
- **Pull Requests:**
  - Ensures that contributions meet our formatting standards before merging.
  - Generates a concise summary of the changes using GPT-4o.
  - Automatically applies relevant labels using GPT-4o for intelligent categorization.
- **Issues:** Automatically applies relevant labels using GPT-4o when new issues are created.

These actions help maintain code quality, improve documentation clarity, and streamline the review process by providing consistent formatting, informative summaries, and appropriate categorization of issues and pull requests.

## 🔧 Setting Up the Action

To use this action in your Ultralytics repository:

1. **Create a Workflow File:** In your repository, create a file under `.github/workflows/`, e.g., `ultralytics-actions.yml`.

2. **Add the Action:** Use the Ultralytics Actions in your workflow file as follows:

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
       runs-on: ubuntu-latest
       steps:
         - name: Run Ultralytics Formatting
           uses: ultralytics/actions@main
           with:
             token: ${{ secrets.GITHUB_TOKEN }} # automatically generated, do not modify
             labels: true # autolabel issues and PRs
             python: true # format Python code and docstrings
             prettier: true # format YAML, JSON, Markdown and CSS
             swift: true # format Swift code (requires 'macos-latest')
             spelling: true # check spelling
             links: true # check broken links
             summary: true # print PR summary with GPT4o (requires 'openai_api_key')
             openai_api_key: # your OpenAI API key
   ```

3. **Customize:** Adjust the workflow settings as necessary for your project.

## 💡 Contribute

Ultralytics thrives on community collaboration; we immensely value your involvement! We urge you to peruse our [Contributing Guide](https://docs.ultralytics.com/help/contributing/) for detailed insights on how you can participate. Don't forget to share your feedback with us by contributing to our [Survey](https://www.ultralytics.com/survey?utm_source=github&utm_medium=social&utm_campaign=Survey). A heartfelt thank you 🙏 goes out to everyone who has already contributed!

<a href="https://github.com/ultralytics/yolov5/graphs/contributors">
<img width="100%" src="https://github.com/ultralytics/assets/raw/main/im/image-contributors.png" alt="Ultralytics open-source contributors"></a>

## 📄 License

Ultralytics presents two distinct licensing paths to accommodate a variety of scenarios:

- **AGPL-3.0 License**: This official [OSI-approved](https://opensource.org/license) open-source license is perfectly aligned with the goals of students, enthusiasts, and researchers who believe in the virtues of open collaboration and shared wisdom. Details are available in the [LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) document.
- **Enterprise License**: Tailored for commercial deployment, this license authorizes the unfettered integration of Ultralytics software and AI models within commercial goods and services, without the copyleft stipulations of AGPL-3.0. Should your use case demand an enterprise solution, direct your inquiries to [Ultralytics Licensing](https://www.ultralytics.com/license).

## 📮 Contact

For bugs or feature suggestions pertaining to Ultralytics, please lodge an issue via [GitHub Issues](https://github.com/ultralytics/pre-commit/issues). You're also invited to participate in our [Discord](https://discord.com/invite/ultralytics) community to engage in discussions and seek advice!

<br>
<div align="center">
  <a href="https://github.com/ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-github.png" width="3%" alt="Ultralytics GitHub"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.linkedin.com/company/ultralytics/"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-linkedin.png" width="3%" alt="Ultralytics LinkedIn"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://twitter.com/ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-twitter.png" width="3%" alt="Ultralytics Twitter"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://youtube.com/ultralytics?sub_confirmation=1"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-youtube.png" width="3%" alt="Ultralytics YouTube"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.tiktok.com/@ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-tiktok.png" width="3%" alt="Ultralytics TikTok"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://ultralytics.com/bilibili"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-bilibili.png" width="3%" alt="Ultralytics BiliBili"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://discord.com/invite/ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-discord.png" width="3%" alt="Ultralytics Discord"></a>
</div>
