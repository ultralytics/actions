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
      timeout_minutes: 30 # Maximum time for each attempt
      retry_delay_seconds: 10 # Base delay between retries
      backoff: exponential # exponential (10s, 20s, 40s, ...) or fixed
      jitter: true # Randomize delay to 80-120% to avoid thundering herd
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

| Input                 | Description                                                  | Required | Default       |
| --------------------- | ------------------------------------------------------------ | -------- | ------------- |
| `run`                 | Command to run                                               | Yes      | -             |
| `retries`             | Number of retry attempts after initial run                   | No       | `3`           |
| `timeout_minutes`     | Maximum time in minutes for each attempt                     | No       | `360`         |
| `retry_delay_seconds` | Base delay between retries in seconds                        | No       | `10`          |
| `backoff`             | Backoff strategy: `exponential` (base \* 2^n) or `fixed`     | No       | `exponential` |
| `jitter`              | Randomize delay to 80-120% of value to avoid thundering herd | No       | `true`        |
| `shell`               | Shell to use (`bash` or `python`)                            | No       | `bash`        |

## ✨ Features

- Preserves environment variables and step context
- Exponential backoff with ±20% jitter (best-practice defaults)
- Configurable per-attempt timeout that terminates hung process trees
- GitHub Actions grouping for retry attempts
- Supports both Bash and Python shells

Timeout supervision requires Python 3 on Linux and macOS.
