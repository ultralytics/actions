<a href="https://www.ultralytics.com/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320" alt="Ultralytics logo"></a>

# 🔄 Step-Level Retry Action

Retries a step while preserving its full context and environment.

## 🚀 Usage

### Basic Usage

Retry failed step up to 3 times (default):

```yaml
steps:
  - uses: ultralytics/actions/retry@main
    with:
      run: python train.py
```

### Advanced Usage

Full configuration with custom retries, timeout, backoff, and jitter:

```yaml
steps:
  - uses: ultralytics/actions/retry@main
    with:
      run: |
        python setup.py install
        pytest tests/
      retries: 2 # Retry twice after initial attempt (3 total runs)
      timeout_minutes: 30 # Total timeout across all attempts
      retry_delay_seconds: 10 # Base delay between retries
      backoff: exponential # exponential (10s, 20s, 40s, ...) or fixed
      max_delay_seconds: 300 # Cap for exponential backoff
      jitter: true # Randomize delay ±50% to avoid thundering herd
      shell: bash # Use python or bash shell
```

### Python Shell Example

```yaml
steps:
  - uses: ultralytics/actions/retry@main
    with:
      shell: python
      retries: 5
      run: |
        import requests
        response = requests.get('https://api.example.com/data')
        response.raise_for_status()
```

## 📋 Inputs

| Input                 | Description                                                        | Required | Default       |
| --------------------- | ------------------------------------------------------------------ | -------- | ------------- |
| `run`                 | Command to run                                                     | Yes      | -             |
| `retries`             | Number of retry attempts after initial run                         | No       | `3`           |
| `timeout_minutes`     | Maximum total time in minutes for all attempts combined            | No       | `360`         |
| `retry_delay_seconds` | Base delay between retries in seconds                              | No       | `10`          |
| `backoff`             | Backoff strategy: `exponential` (base \* 2^n, capped) or `fixed`   | No       | `exponential` |
| `max_delay_seconds`   | Maximum delay between retries in seconds (exponential backoff cap) | No       | `300`         |
| `jitter`              | Randomize delay ±50% to spread retries and avoid thundering herd   | No       | `true`        |
| `shell`               | Shell to use (`bash` or `python`)                                  | No       | `bash`        |

## ✨ Features

- Preserves environment variables and step context
- Exponential backoff with configurable cap and equal jitter (best-practice defaults)
- Configurable total timeout across all attempts
- GitHub Actions grouping for retry attempts
- Supports both Bash and Python shells
