# Setup uv Action

Provides Ultralytics defaults for the official [uv setup action](https://github.com/astral-sh/setup-uv): the latest uv release with the latest known release as a fallback, and an activated venv built on the newest Python preinstalled on the runner, so no Python download is needed. The venv lives in `$RUNNER_TEMP/.venv`, outside the workspace, so checkouts, builds and repository scans never see it. Requested versions that are not preinstalled are downloaded by uv.

## Usage

```yaml
- uses: ultralytics/actions/setup-uv@main
- run: uv pip install -e .
```

Set `activate-environment: false` when the job manages its own environment (self-hosted runners, conda) or the action runs before checkout.

## Inputs

| Input                  | Description                               | Required | Default                       |
| ---------------------- | ----------------------------------------- | -------- | ----------------------------- |
| `python-version`       | Python version for uv commands            | No       | Newest preinstalled on runner |
| `activate-environment` | Create and activate a venv in runner temp | No       | `true`                        |
| `enable-cache`         | Cache uv downloads between workflow runs  | No       | `false`                       |
| `ignore-empty-workdir` | Suppress warnings for an empty workdir    | No       | `false`                       |
