# AGENTS.md

Repository guidance for coding agents. `CLAUDE.md` is a symlink to this file.

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

## Commands and validation

```bash
uv venv --python 3.14
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest tests -v
pytest tests/test_first_interaction.py -v
ruff format --line-length 120 .
```

Keep Python 3.8 compatibility; CI also runs a recent Python. Formatter flags are owned by `action.yml` and mirrored in `actions/format_code.py`: update both, including codespell lists. Run pytest from the repository root; the real Markdown formatter test can rewrite files, so inspect the working tree afterward. Missing `shfmt` is only logged. See `.github/workflows/ci.yml` for the full check matrix.

## Where to look

- Formatting → `action.yml`, `actions/format_code.py`.
- Reviews and summaries → `actions/review_pr.py`, `actions/first_interaction.py`.
- Models and prompts → `actions/utils/openai_utils.py`.
- GitHub requests → `actions/utils/github_utils.py`.
- Headers and Markdown → `actions/update_file_headers.py`, `actions/update_markdown_code_blocks.py`.
- Release gating → `actions/utils/version_utils.py`, `.github/workflows/publish.yml`.

## Conventions

- Ultralytics-owned PyPI packages use `MAJOR.MINOR.PATCH` versions only; no suffixes.
- License headers (`# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license`) are added automatically by Ultralytics Actions (`ultralytics-actions-headers`, extensions in `COMMENT_MAP`) — don't add or revert them manually.
- Bump `__version__` in `actions/__init__.py` when a PR changes package behavior — publishing to PyPI is gated on the version change (`publish.yml`).
- Google-style docstrings, single-line summaries where possible; formatting is enforced by the repo's own action (`format.yml`), which auto-commits fixes to PRs.
- Tests use `unittest.mock`/`monkeypatch` to patch env vars and network calls; no test reaches the network (`tests/test_urls.py` patches `is_url` with an autouse fixture and calls it with `check=False`). Modules listed in `[tool.coverage.run] omit` are excluded from the coverage report.
- Commits and PRs use plain git identity — no AI attribution, co-author lines, or generated-with footers.

## Pitfalls

- Env is read at import time into module constants: `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`MODEL`/`REVIEW_MODEL` (`openai_utils.py`), `LABELS`→`AUTO_LABELS`, `SUMMARY`→`AUTO_PR_SUMMARY`, `REVIEW`→`AUTO_PR_REVIEW`, `BLOCK_USER` (`first_interaction.py`), `CURRENT_TAG`/`PREVIOUS_TAG` (`summarize_release.py`), `HEADER` (`update_file_headers.py`). Setting `os.environ` after import has no effect — patch the module attribute (e.g. `patch("actions.utils.openai_utils.OPENAI_API_KEY", "x")`, `patch("actions.first_interaction.AUTO_PR_REVIEW", False)`).
- `_verified_local_checkout` depends only on whether the reviewed commit exists in the runner's git objects, not on the event type. The root `action.yml` checks out the PR head only for `pull_request` events, so under `pull_request_target` the review reads files through the GitHub API and drops the `search_repo` tool unless the consumer workflow checked out that head itself.
- `Action`'s session retries connection failures on every method but 5xx responses only on `GET`/`PUT`/`DELETE`; a `POST`/`PATCH` that returns 5xx is not retried by the session — callers such as `cla._read`/`_persist` and `get_response` implement their own loops.
- `publish.yml`'s `check` job gates releases with the **PyPI-installed** `ultralytics-actions` (`shell: python` temp script plus the `ultralytics-actions-summarize-release` console script, neither of which sees the checkout's `actions/`), so a change to `version_utils.py` or `summarize_release.py` only affects the next release after it is itself published.
- The `Alert` label path in `apply_and_check_labels` rewrites the title/body, locks, and (for issues/discussions) closes the item for a non-org member as soon as the model returns `Alert` and the repository has that label; `BLOCK_USER=true` additionally blocks the account org-wide.
