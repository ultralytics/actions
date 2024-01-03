<br>
<img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320">

# 🚀 Ultralytics Actions: Auto-Formatting for Python and Markdown

Welcome to the [Ultralytics Actions](https://github.com/ultralytics/action) repository, your go-to solution for maintaining consistent code quality across Ultralytics Python projects. This GitHub Action is designed to automate the formatting of Python and Markdown files, ensuring adherence to our coding standards.



## 📄 Actions Description

Ultralytics Actions automatically applies formats and updates:

- **Python Code:** Using [Ruff](https://github.com/charliermarsh/ruff), a fast Python auto-formatter.
- **Markdown Files:** With [mdformat](https://github.com/executablebooks/mdformat), ensuring a consistent style in documentation.
- **Docstrings:** Utilizing [docformatter](https://github.com/myint/docformatter) for clean and standardized documentation comments.
- **Spell Check:** Employing [codespell](https://github.com/codespell-project/codespell) for catching common misspellings.

## 🛠 How It Works

Upon integration, Ultralytics Actions triggers on:

- **Push Events:** Automatically formats code when changes are pushed to the `main` branch.
- **Pull Requests:** Ensures that contributions meet our formatting standards before merging.

## 🔧 Setting Up the Action

To use this action in your Ultralytics repository:

1. **Create a Workflow File:** In your repository, create a file under `.github/workflows/`, e.g., `format-code.yml`.
2. **Add the Action:** Use the Ultralytics Actions in your workflow file as follows:
   ```yaml
   name: Ultralytics Actions

   on:
     push:
       branches: [main]
     pull_request:
       branches: [main]

   jobs:
     format:
       runs-on: ubuntu-latest
       steps:
         - name: Run Ultralytics Formatting
           uses: ultralytics/actions@main
           with:
             python: true
             docstrings: true
             markdown: true
             spelling: true
   ```
3. **Customize:** Adjust the workflow settings as necessary for your project.

## 💡 Contribute

Ultralytics thrives on community collaboration; we immensely value your involvement! We urge you to peruse our [Contributing Guide](https://docs.ultralytics.com/help/contributing) for detailed insights on how you can participate. Don't forget to share your feedback with us by contributing to our [Survey](https://ultralytics.com/survey?utm_source=github&utm_medium=social&utm_campaign=Survey). A heartfelt thank you 🙏 goes out to everyone who has already contributed!

<a href="https://github.com/ultralytics/yolov5/graphs/contributors">
<img width="100%" src="https://github.com/ultralytics/assets/raw/main/im/image-contributors.png" alt="Ultralytics open-source contributors"></a>

## 📄 License

Ultralytics presents two distinct licensing paths to accommodate a variety of scenarios:

- **AGPL-3.0 License**: This official [OSI-approved](https://opensource.org/licenses/) open-source license is perfectly aligned with the goals of students, enthusiasts, and researchers who believe in the virtues of open collaboration and shared wisdom. Details are available in the [LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) document.
- **Enterprise License**: Tailored for commercial deployment, this license authorizes the unfettered integration of Ultralytics software and AI models within commercial goods and services, without the copyleft stipulations of AGPL-3.0. Should your use case demand an enterprise solution, direct your inquiries to [Ultralytics Licensing](https://ultralytics.com/license).

## 📮 Contact

For bugs or feature suggestions pertaining to Ultralytics, please lodge an issue via [GitHub Issues](https://github.com/ultralytics/pre-commit/issues). You're also invited to participate in our [Discord](https://ultralytics.com/discord) community to engage in discussions and seek advice!

<br>
<div align="center">
  <a href="https://github.com/ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-github.png" width="3%" alt="Ultralytics GitHub"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.linkedin.com/company/ultralytics/"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-linkedin.png" width="3%" alt="Ultralytics LinkedIn"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://twitter.com/ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-twitter.png" width="3%" alt="Ultralytics Twitter"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://youtube.com/ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-youtube.png" width="3%" alt="Ultralytics YouTube"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.tiktok.com/@ultralytics"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-tiktok.png" width="3%" alt="Ultralytics TikTok"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://www.instagram.com/ultralytics/"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-instagram.png" width="3%" alt="Ultralytics Instagram"></a>
  <img src="https://github.com/ultralytics/assets/raw/main/social/logo-transparent.png" width="3%" alt="space">
  <a href="https://ultralytics.com/discord"><img src="https://github.com/ultralytics/assets/raw/main/social/logo-social-discord.png" width="3%" alt="Ultralytics Discord"></a>
</div>
