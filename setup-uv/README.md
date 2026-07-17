# Setup uv Action

Installs the latest [uv](https://docs.astral.sh/uv/) release with retry support and optionally activates a Python virtual environment.

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

| Input                   | Description                               | Required | Default      |
| ----------------------- | ----------------------------------------- | -------- | ------------ |
| `python-version`        | Python version for uv commands            | No       | -            |
| `activate-environment`  | Create and activate a `.venv` environment | No       | `false`      |
| `enable-cache`          | Cache uv downloads between workflow runs  | No       | `false`      |
| `cache-dependency-glob` | Dependency files used to invalidate cache | No       | `**/uv.lock` |
