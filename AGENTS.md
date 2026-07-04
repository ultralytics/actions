# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, etc.) when working with code in this repository. CLAUDE.md is a symlink to this file.

## Core Principles (CRITICAL)

Respecting these principles is critical for every PR.

**Less is more. The simplest solution is the best solution.**

The action hierarchy for every change: **Delete > Replace > Add**. The best code change is a deletion. The second best is modifying what exists. Adding new code is the last resort.

1. **Minimal**: The simplest solution that works. Do not over-engineer, over-abstract, or add code just in case. Three similar lines beat a premature abstraction. Avoid error handling for impossible states, feature flags, compatibility shims, or policy scaffolding unless they are truly required.
2. **Solve at the source**: Do not hack fixes. Solve problems at their root. If something is broken, fix or remove the broken thing. Never patch over a broken abstraction, add workarounds, or add synchronization code for state that should not be duplicated.
3. **Delete ruthlessly**: When replacing code, delete what it replaced. Remove unused imports, functions, types, files, and commented-out code. Git preserves history. Run the repo's relevant dead-code or cleanup check when available.
4. **Replace > Add**: Modify existing code over adding new code. Edit existing files, extend existing components or functions with minimal parameters, and reuse existing utilities. If creating a new file, first prove it cannot fit cleanly in an existing file.
5. **Check existing**: Search the entire repo before creating anything new. If a feature, component, helper, responder, workflow, or utility already solves a similar problem, reuse or adapt it and delete the duplicate path.
6. **Deduplicate**: Do not duplicate existing code when updating the repo. Consolidate or refactor duplicates you find when it is in scope and low risk.
7. **Zero Regression**: Do not break existing features or workflows unless the PR intentionally removes them with evidence.
8. **Production ready**: All changes must be thoroughly debugged, validated, and production ready.

**When fixing bugs, ask: "What can I delete?" before "What can I replace?" before "What should I add?"**

## PR Workflow

After opening a PR:

1. Wait for the automated PR review and auto-format commit from Ultralytics Actions (`format.yml`), then pull and address every finding.
2. Launch an independent adversarial review agent with cold context (no prior conversation, just the PR diff and this file) to hunt for bugs, regressions, and Core Principles violations. Fix what it finds, push, and repeat with a fresh agent until one reports LGTM with zero findings.

## Commands

```bash
pip install -e ".[dev]" # install for development (or: uv pip install --system -e ".[dev]")

pytest tests -v                                             # run all tests
pytest tests/test_common_utils.py -v                        # run one test file
pytest tests/test_github_utils.py::test_name -v             # run one test
pytest tests -v --cov=actions --cov-report=xml:coverage.xml # tests with coverage (CI command)

ruff check --fix --unsafe-fixes --extend-select F,I,D,UP,RUF,FA --target-version py39 \
  --ignore D100,D104,D203,D205,D212,D213,D401,D406,D407,D413,RUF001,RUF002,RUF012 .
ruff format --line-length 120 . # format (line length 120)
```

Notes:

- `pytest` is configured with `--doctest-modules`, so docstring examples in `actions/` are also executed as tests.
- CI tests Python 3.8 and 3.14 on ubuntu and macos — code must stay 3.8-compatible. Use `from __future__ import annotations` for modern type hints (the codebase does this everywhere).
- CI also smoke-tests every CLI entry point (`tests/test_cli_commands.py`).

## Architecture

This repo is two things at once:

1. **A Python package (`actions/`)** published as `ultralytics-actions` on PyPI. Each top-level module (`first_interaction.py`, `review_pr.py`, `summarize_pr.py`, `summarize_release.py`, `dependabot.py`, `github_report.py`, etc.) is a standalone script exposed as a `ultralytics-actions-*` CLI entry point in `pyproject.toml` `[project.scripts]`.
2. **GitHub composite actions.** The root `action.yml` is the main "Ultralytics Actions" marketplace action: it installs the Python package, then runs formatters (Ruff, Prettier, Biome, swift-format, dart format, codespell) and the CLI entry points conditioned on event type and inputs, then commits results back to the PR. Subdirectories `retry/`, `cleanup-disk/`, `dependabot/`, `github-report/` are standalone composite actions with their own `action.yml` + README.

Key flow: GitHub workflow event → `action.yml` step (gated by `github.event_name` / `github.event.action` / inputs) → env vars (`GITHUB_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MODEL`, ...) → CLI entry point → module `main()`/`run()`.

`actions/utils/` is the shared core:

- **`github_utils.py`** — the `Action` class, the central abstraction. Initializes from GitHub Actions env vars (`GITHUB_TOKEN`, `GITHUB_EVENT_NAME`, `GITHUB_EVENT_PATH`), wraps REST (`get`/`post`/`patch`/...) and GraphQL requests with unified status checking, and provides high-level operations (PR diffs, labels, comments, discussions, alerts).
- **`openai_utils.py`** — AI provider abstraction supporting OpenAI and Anthropic. The provider/model is auto-detected from which API key env var is set; defaults live here as single source of truth (`OPENAI_MODEL_DEFAULT`, `ANTHROPIC_MODEL_DEFAULT`, `PR_REVIEW_MODEL_DEFAULT`, `MODEL_COSTS`). Also holds shared prompt-building and response sanitization.
- **`common_utils.py`** — URL/redirect checking, diff filtering, file-skip patterns, HTML comment removal.
- **`version_utils.py`** — PyPI/pub.dev version checks used for publish gating.

Everything reusable is re-exported through `actions/utils/__init__.py` — import from `actions.utils`, and keep `__all__` updated when adding exports.

Self-hosting detail: when a workflow runs inside `ultralytics/actions` itself, `action.yml` installs the package from the current git branch (not PyPI/main), so PRs here dogfood their own changes via `.github/workflows/format.yml`.

The package version lives in `actions/__init__.py` (`__version__`); publishing to PyPI is gated on version bumps (`publish.yml`).

## Conventions

- Every file starts with the header `# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license` (enforced by `ultralytics-actions-headers`).
- Google-style docstrings, single-line summaries where possible; formatting is enforced by the repo's own action (`format.yml`), which auto-commits fixes to PRs.
- Tests use `unittest.mock` to patch env vars and network calls — no real GitHub/OpenAI requests in tests. Modules listed in `[tool.coverage.run] omit` are excluded from coverage requirements.
- Commits and PRs use plain git identity — no AI attribution, co-author lines, or generated-with footers.
