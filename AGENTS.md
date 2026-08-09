# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, etc.) when working with code in this repository. CLAUDE.md is a symlink to this file.

Ultralytics Actions (`ultralytics-actions` on PyPI, AGPL-3.0) is the GitHub automation toolkit used across the Ultralytics organization: it formats code and documentation, auto-labels issues and PRs, generates AI PR summaries and reviews, and ships supporting composite actions for CI retries, disk cleanup, Dependabot updates, and GitHub reporting.

## Core Principles (CRITICAL)

**Less is more. The simplest solution is the best solution.** The action hierarchy for every change: **Delete > Replace > Add**.

1. **Solve at the owner**: Put behavior in the code path that owns or observes it. For fixes, never guard a symptom with a staleness check, initialization flag, skip-first-call branch, or `try/except` around broken logic; relocate the trigger and delete the wrong path. For features, extend the existing owner rather than creating a parallel abstraction.
2. **Search and reuse first**: Search the whole repository before creating a feature, component, helper, workflow, or utility. Reuse or adapt what exists, consolidate in-scope duplication in the shared owner, and delete duplicate paths. Three similar lines beat a helper nobody else calls.
3. **Delete and modify existing code before creating new code**: Bugfixes are net-negative by default unless deletion and relocation are demonstrably impossible. A new file must first prove it cannot fit cleanly in an existing owner.
4. **Keep scope minimal**: Implement only the simplest complete solution. Avoid impossible-state handling, speculative flags, compatibility shims, policy scaffolding, and unrelated cleanup. Tests are out of scope by default — rely on existing coverage and focused validation; only an uncovered, high-risk regression path justifies minimal new test code.
5. **Ship zero-regression, production-ready changes**: Understand what you remove instead of retaining broken code as insurance. Remove unused imports, functions, types, files, and comments; run relevant cleanup checks; and thoroughly debug and validate the changed owner. Do not break existing features or workflows unless the PR intentionally removes them with evidence.

**Review gate:** for every addition, the reviewer decides whether deleting or changing existing code would have fixed the problem instead — if it would, that is a blocking finding. A missing or thin PR description is never itself a finding.

NEVER push to `main`. NEVER force push. Always start work in a new git worktree (`git worktree add`) on a feature branch and open a PR — never edit the primary checkout directly, it may hold in-flight work.

## PR Workflow

After opening a PR:

1. Wait for the automated PR review and auto-format commit from Ultralytics Actions (`format.yml`), then pull and address every finding.
2. Review the full diff in-session against the Core Principles, performance, and the review gate above, then batch the fixes into one commit and push. After each round of bot or human commits, pull and resume the same reviewer on `<last-reviewed-sha>..HEAD` plus anything that delta could have invalidated. Repeat until the local head matches the live head.
3. Hand off or merge only on a clean final pass: one cold full-diff review returning LGTM with no findings, on a head that is still live at merge time.
4. Never fight other commits: Ultralytics Actions pushes auto-format and header commits, and multiple users may work on the same PR. `git pull --rebase` before pushing; never reset or revert commits you did not author.
5. After the PR merges, clean up: remove local worktrees and branches for it, then `git checkout main && git pull`.

## Commands

```bash
uv pip install -e ".[dev]" # install for development

pytest tests -v                                             # run all tests
pytest tests/test_common_utils.py -v                        # run one test file
pytest tests/test_github_utils.py::test_name -v             # run one test
pytest tests -v --cov=actions --cov-report=xml:coverage.xml # tests with coverage (CI command)

# Lint/format — mirrors the "Run Python" step in action.yml (source of truth if these drift)
ruff check --fix --unsafe-fixes --extend-select F,I,D,UP,RUF,FA --target-version py38 \
  --ignore BLE001,D100,D104,D203,D205,D212,D213,D401,D406,D407,D413,RUF001,RUF002,RUF012,S110 .
ruff format --line-length 120 .
```

Notes:

- CI tests Python 3.8 and 3.14 on ubuntu and macos — code must stay 3.8-compatible. Use `from __future__ import annotations` for modern type hints.

## Architecture

This repo is two things at once:

1. **A Python package (`actions/`)** published as `ultralytics-actions` on PyPI. Top-level modules (`first_interaction.py`, `review_pr.py`, `summarize_pr.py`, `summarize_release.py`, `dependabot.py`, `github_report.py`, etc.) are standalone scripts, most exposed as `ultralytics-actions-*` CLI entry points in `pyproject.toml` `[project.scripts]`.
2. **GitHub composite actions.** The root `action.yml` is the main "Ultralytics Actions" marketplace action: it installs the Python package, then runs formatters (Ruff, Prettier, Biome, swift-format, dart format, codespell) and the CLI entry points conditioned on event type and inputs, then commits results back to the PR. Subdirectories `retry/`, `cleanup-disk/`, `dependabot/`, `github-report/` are standalone composite actions with their own `action.yml` + README.

Key flow: GitHub workflow event → `action.yml` step (gated by `github.event_name` / `github.event.action` / inputs) → env vars (`GITHUB_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MODEL`, ...) → CLI entry point → module `main()`/`run()`.

`actions/utils/` is the shared core:

- **`github_utils.py`** — the `Action` class, the central abstraction. Initializes from GitHub Actions env vars (`GITHUB_TOKEN`, `GITHUB_EVENT_NAME`, `GITHUB_EVENT_PATH`), wraps REST (`get`/`post`/`patch`/...) and GraphQL requests with unified status checking, and provides high-level operations (PR diffs, labels, comments, discussions, alerts).
- **`openai_utils.py`** — AI provider abstraction supporting OpenAI and Anthropic. The provider/model is auto-detected from which API key env var is set; defaults live here as single source of truth (`OPENAI_MODEL_DEFAULT`, `ANTHROPIC_MODEL_DEFAULT`, `OPENAI_REVIEW_MODEL_DEFAULT`, `ANTHROPIC_REVIEW_MODEL_DEFAULT`, `MODEL_COSTS`). Also holds shared prompt-building and response sanitization.
- **`common_utils.py`** — URL/redirect checking, diff filtering, file-skip patterns, HTML comment removal.
- **`version_utils.py`** — PyPI/pub.dev version checks used for publish gating.

Most shared utilities are re-exported through `actions/utils/__init__.py` — keep `__all__` updated when adding exports.

Security detail: `.github/workflows/format.yml` runs `ultralytics/actions@main` because it receives write credentials and AI secrets; never execute a PR checkout as a local action in that workflow. PR package changes are exercised by the test workflow before merge.

## Conventions

- License headers (`# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license`) are added automatically by Ultralytics Actions (`ultralytics-actions-headers`, extensions in `COMMENT_MAP`) — don't add or revert them manually.
- Bump `__version__` in `actions/__init__.py` when a PR changes package behavior — publishing to PyPI is gated on the version change (`publish.yml`).
- Google-style docstrings, single-line summaries where possible; formatting is enforced by the repo's own action (`format.yml`), which auto-commits fixes to PRs.
- Tests use `unittest.mock` to patch env vars and network calls, except `tests/test_urls.py` which makes live HTTP requests. Modules listed in `[tool.coverage.run] omit` are excluded from coverage requirements.
- Commits and PRs use plain git identity — no AI attribution, co-author lines, or generated-with footers.
