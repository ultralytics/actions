<a href="https://www.ultralytics.com/"><img src="https://raw.githubusercontent.com/ultralytics/assets/main/logo/Ultralytics_Logotype_Original.svg" width="320" alt="Ultralytics logo"></a>

# 🧹 Disk Space Cleanup Action

Cleans up disk space on GitHub Actions runners by removing unnecessary tool caches and swap space. Frees up ~19GB total space.

## 🚀 Usage

### Basic Usage

Add as early step in jobs requiring disk space:

```yaml
steps:
  - uses: ultralytics/actions/cleanup-disk@main

  - name: Run disk-intensive task
    run: |
      docker build -t myimage .
      pytest --large-files
```

### Complete Workflow Example

```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ultralytics/actions/cleanup-disk@main

      - name: Build and test
        run: |
          pip install -e .
          pytest
```

### With Other Actions

```yaml
steps:
  - uses: actions/checkout@v4

  - uses: ultralytics/actions/cleanup-disk@main

  - uses: docker/setup-buildx-action@v3

  - name: Build Docker image
    run: docker build -t myapp .
```

## 🗑️ What Gets Cleaned

- `/opt/hostedtoolcache` - Tool cache (~15GB)
- `/swapfile` - Swap space (~4GB)

## 💡 When to Use

Use this action when your workflow:

- Builds large Docker images
- Processes large datasets or files
- Runs out of disk space on GitHub-hosted runners
- Requires more than the default ~14GB available space

## 📊 Before/After

The action displays disk space before and after cleanup:

```
Free space before deletion:
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        84G   60G   24G  72% /

Free space after deletion:
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        84G   41G   43G  49% /
```
