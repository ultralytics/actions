# Setup uv Action

Provides Ultralytics defaults for the official [uv setup action](https://github.com/astral-sh/setup-uv), using its latest checksum-verified uv release without a manifest request and optionally activating a Python environment and dependency caching.

## Usage

```yaml
- uses: ultralytics/actions/setup-uv@main
  with:
    python-version: "3.14"
    activate-environment: true
    enable-cache: true
    cache-dependency-glob: "pyproject.toml"
```

## Inputs

| Input                   | Description                               | Required | Default        |
| ----------------------- | ----------------------------------------- | -------- | -------------- |
| `version`               | uv version or selector to install         | No       | `latest-known` |
| `python-version`        | Python version for uv commands            | No       | -              |
| `activate-environment`  | Create and activate a `.venv` environment | No       | `false`        |
| `enable-cache`          | Cache uv downloads between workflow runs  | No       | `false`        |
| `cache-dependency-glob` | Dependency files used to invalidate cache | No       | `**/uv.lock`   |
| `ignore-empty-workdir`  | Suppress warnings for an empty workdir    | No       | `false`        |
