# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, etc.) when working with code in this repository. CLAUDE.md is a symlink to this file.

## Core Principles (CRITICAL)

**Less is more. The simplest solution is the best solution.** The action hierarchy for every change: **Delete > Replace > Add**. The best code change is a deletion, the second best is modifying what exists, and adding new code is the last resort.

1. **Solve at the owner**: Put behavior in the code path that owns or observes it. For fixes, never guard a symptom with a staleness check, initialization flag, skip-first-call branch, or `try/except` around broken logic; relocate the trigger and delete the wrong path. For features, extend the existing owner rather than creating a parallel abstraction.
2. **Search and reuse first**: Search the whole repository before creating a helper, utility, composite action, or workflow — most shared code belongs in `actions/utils/`. Reuse or adapt what exists, consolidate in the shared owner when duplication appears, and delete duplicate paths. Three similar lines beat a helper nobody else calls.
3. **Delete and modify existing code before creating new code**: Bugfixes are net-negative by default; a net-positive bugfix needs a one-sentence PR justification explaining why deletion or relocation was impossible. A new file must first prove it cannot fit cleanly in an existing owner.
4. **Keep scope minimal**: Implement only the simplest complete solution. Avoid impossible-state handling, speculative flags, compatibility shims, policy scaffolding, and unrelated cleanup. Tests are out of scope by default — rely on existing coverage and focused validation; only an uncovered, high-risk regression path justifies minimal new test code.
5. **Ship zero-regression, production-ready changes**: Understand what you remove instead of retaining broken code as insurance. Remove unused imports, functions, types, files, and comments; run relevant cleanup checks; and thoroughly debug and validate the changed owner. Do not break existing workflows unless the PR intentionally removes them with evidence.

**Review gate:** for every addition, the reviewer inspects the surrounding code and decides whether deleting or changing what already exists would have fixed the problem instead — if it would, that is a blocking finding. Judge the diff, never the PR description; a missing explanation is not a finding.

NEVER push to `main`. NEVER force push. Always start work in a new git worktree (`git worktree add`) on a feature branch and open a PR — never edit the primary checkout directly, it may hold in-flight work.

## PR Workflow

After opening a PR:

1. Wait for the automated PR review and auto-format commit from Ultralytics Actions (`format.yml`), then pull and address every finding.
2. Launch an independent adversarial review agent with cold context (just the PR diff and this file) to hunt for bugs, regressions, and Core Principles violations. Fix, push, and repeat with a fresh agent until one reports LGTM.
3. Never fight other commits: Ultralytics Actions pushes auto-format and header commits, and multiple users may work on the same PR. `git pull --rebase` before pushing; never reset or revert commits you did not author.
4. After the PR merges, clean up: remove local worktrees and branches for it, then `git checkout main && git pull`.

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
- **`openai_utils.py`** — AI provider abstraction supporting OpenAI and Anthropic. The provider/model is auto-detected from which API key env var is set; defaults live here as single source of truth (`OPENAI_MODEL_DEFAULT`, `ANTHROPIC_MODEL_DEFAULT`, `PR_REVIEW_MODEL_DEFAULT`, `MODEL_COSTS`). Also holds shared prompt-building and response sanitization.
- **`common_utils.py`** — URL/redirect checking, diff filtering, file-skip patterns, HTML comment removal.
- **`version_utils.py`** — PyPI/pub.dev version checks used for publish gating.

Most shared utilities are re-exported through `actions/utils/__init__.py` — keep `__all__` updated when adding exports.

Self-hosting detail: `.github/workflows/format.yml` checks out the event's ref (PR head for pull requests, main for issue events) and runs `uses: ./` — so PRs here dogfood both the Python package and `action.yml` itself before merge.

## Conventions

- License headers (`# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license`) are added automatically by Ultralytics Actions (`ultralytics-actions-headers`, extensions in `COMMENT_MAP`) — don't add or revert them manually.
- Bump `__version__` in `actions/__init__.py` when a PR changes package behavior — publishing to PyPI is gated on the version change (`publish.yml`).
- Google-style docstrings, single-line summaries where possible; formatting is enforced by the repo's own action (`format.yml`), which auto-commits fixes to PRs.
- Tests use `unittest.mock` to patch env vars and network calls, except `tests/test_urls.py` which makes live HTTP requests. Modules listed in `[tool.coverage.run] omit` are excluded from coverage requirements.
- Commits and PRs use plain git identity — no AI attribution, co-author lines, or generated-with footers.
