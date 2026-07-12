# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import urllib.error
from datetime import datetime, timedelta, timezone

from actions import failed_scheduled_actions, github_report


def test_paginate_only_skips_http_errors_when_allowed(monkeypatch):
    """Org-level auth failures should raise, while allowed per-repo misses can be skipped."""

    def fake_get(path, params=None, token=None, allow_skip=False):
        if allow_skip:
            return None
        raise PermissionError(path)

    monkeypatch.setattr(failed_scheduled_actions, "github_get", fake_get)

    assert failed_scheduled_actions.paginate("/repos/ultralytics/repo/actions/runs", allow_skip=True) == []

    try:
        failed_scheduled_actions.paginate("/orgs/ultralytics/repos")
    except PermissionError as e:
        assert str(e) == "/orgs/ultralytics/repos"
    else:
        raise AssertionError("Expected org listing failure to raise")


def test_failed_scheduled_actions_visibility_guards(capsys):
    """Invalid and unsafe visibility inputs fall back to public repositories."""
    assert failed_scheduled_actions.parse_visibility("public,invalid", "private") == ["public"]
    assert failed_scheduled_actions.parse_visibility("invalid", "private") == ["public"]
    assert failed_scheduled_actions.parse_visibility("private", "public") == ["public"]

    output = capsys.readouterr().out
    assert "Invalid visibility values: invalid" in output
    assert "No valid visibility values" in output
    assert "Restricting to public only" in output


def test_github_get_requires_token(monkeypatch):
    """GitHub API calls require an auth token."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    try:
        failed_scheduled_actions.github_get("/user")
    except RuntimeError as e:
        assert str(e) == "GH_TOKEN or GITHUB_TOKEN is required"
    else:
        raise AssertionError("Expected missing token to raise")


def test_github_get_fetches_json(monkeypatch):
    """GitHub API responses are decoded from the requested URL."""
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        requests.append((request.full_url, timeout, request.headers["Authorization"]))
        if len(requests) == 1:
            raise urllib.error.HTTPError("url", 504, "Gateway Timeout", {}, None)
        return Response()

    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setattr(failed_scheduled_actions.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(failed_scheduled_actions.time, "sleep", lambda _: None)

    assert failed_scheduled_actions.github_get("/repos/ultralytics/actions", {"page": 1}) == {"ok": True}
    assert requests == [("https://api.github.com/repos/ultralytics/actions?page=1", 60, "Bearer token")] * 2


def test_github_get_skips_allowed_repo_errors(monkeypatch, capsys):
    """Allowed per-repo 403/404 API misses are skipped unless they are rate limits."""

    class Body:
        def __init__(self, text):
            self.text = text

        def read(self):
            return self.text

        def close(self):
            pass

    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setattr(
        failed_scheduled_actions.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("url", 404, "Not Found", {"X-RateLimit-Remaining": "1"}, Body(b"missing"))
        ),
    )

    assert failed_scheduled_actions.github_get("/repos/missing/actions/runs", allow_skip=True) is None
    assert "Skipping /repos/missing/actions/runs: 404" in capsys.readouterr().out

    monkeypatch.setattr(
        failed_scheduled_actions.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("url", 403, "Forbidden", {"X-RateLimit-Remaining": "0"}, Body(b"rate limit"))
        ),
    )
    try:
        failed_scheduled_actions.github_get("/orgs/ultralytics/repos", allow_skip=True)
    except urllib.error.HTTPError as e:
        assert e.code == 403
    else:
        raise AssertionError("Expected rate limit to raise")


def test_paginate_collects_until_short_page(monkeypatch):
    """Pagination stops after the first short page and sleeps between full pages."""
    pages = [
        [{"id": i} for i in range(100)],
        [{"id": 100}],
    ]
    sleeps = []

    def fake_get(path, params=None, token=None, allow_skip=False):
        assert path == "/items"
        return pages[params["page"] - 1]

    monkeypatch.setattr(failed_scheduled_actions, "github_get", fake_get)
    monkeypatch.setattr(failed_scheduled_actions.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert len(failed_scheduled_actions.paginate("/items")) == 101
    assert sleeps == [0.2]


def test_collect_failed_actions_latest_run_per_workflow(monkeypatch):
    """Only the latest default-branch run for each workflow should determine whether it is reported."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    recent_success = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    older_failure = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    recent_failure = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    recent_failure_updated = (now - timedelta(hours=1, minutes=50)).isoformat().replace("+00:00", "Z")

    def fake_paginate(path, params=None, key=None, max_pages=100, token=None, allow_skip=False):
        if path == "/orgs/ultralytics/repos":
            return [
                {
                    "full_name": "ultralytics/private-repo",
                    "html_url": "https://github.com/ultralytics/private-repo",
                    "default_branch": "main",
                    "visibility": "private",
                    "archived": False,
                },
                {
                    "full_name": "ultralytics/public-repo",
                    "default_branch": "main",
                    "visibility": "public",
                    "archived": False,
                },
            ]
        if path == "/repos/ultralytics/private-repo/actions/runs":
            return [
                {
                    "workflow_id": 1,
                    "name": "Nightly",
                    "conclusion": "success",
                    "run_started_at": recent_success,
                },
                {
                    "workflow_id": 1,
                    "name": "Nightly",
                    "conclusion": "failure",
                    "run_started_at": older_failure,
                },
                {
                    "workflow_id": 2,
                    "name": "Links",
                    "event": "push",
                    "conclusion": "timed_out",
                    "run_started_at": recent_failure,
                    "run_number": 42,
                    "updated_at": recent_failure_updated,
                    "head_sha": "abcdef123456",
                    "display_title": "Links",
                    "html_url": "https://github.com/ultralytics/private-repo/actions/runs/42",
                },
            ]
        if path == "/repos/ultralytics/public-repo/actions/runs":
            return []
        raise AssertionError(path)

    monkeypatch.setattr(failed_scheduled_actions, "paginate", fake_paginate)

    failures = failed_scheduled_actions.collect_failed_actions(
        visibility="all", repo_visibility="private", days=3, token="token"
    )

    assert len(failures) == 1
    assert failures[0]["repo"] == "ultralytics/private-repo"
    assert failures[0]["workflow"] == "Links"
    assert failures[0]["event"] == "push"
    assert failures[0]["sha"] == "abcdef1"


def test_collect_failed_actions_ignores_latest_success(monkeypatch):
    """Older failed runs should not be reported after a newer success."""

    def fake_paginate(path, params=None, key=None, max_pages=100, token=None, allow_skip=False):
        if path == "/orgs/ultralytics/repos":
            return [
                {
                    "full_name": "ultralytics/repo",
                    "default_branch": "main",
                    "visibility": "public",
                    "archived": False,
                }
            ]
        if path == "/repos/ultralytics/repo/actions/runs":
            return [
                {
                    "workflow_id": 1,
                    "name": "Nightly",
                    "conclusion": "success",
                    "run_started_at": "2026-06-30T03:00:00Z",
                },
                {
                    "workflow_id": 1,
                    "name": "Nightly",
                    "conclusion": "failure",
                    "run_started_at": "2026-06-29T03:00:00Z",
                },
            ]
        raise AssertionError(path)

    monkeypatch.setattr(failed_scheduled_actions, "paginate", fake_paginate)

    assert failed_scheduled_actions.collect_failed_actions(token="token") == []


def test_collect_failed_actions_respects_days_window(monkeypatch):
    """Failed runs older than the requested window should be omitted."""
    old_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake_paginate(path, params=None, key=None, max_pages=100, token=None, allow_skip=False):
        if path == "/orgs/ultralytics/repos":
            return [
                {
                    "full_name": "ultralytics/repo",
                    "default_branch": "main",
                    "visibility": "public",
                    "archived": False,
                }
            ]
        if path == "/repos/ultralytics/repo/actions/runs":
            return [
                {
                    "workflow_id": 1,
                    "name": "Nightly",
                    "conclusion": "failure",
                    "run_started_at": old_date,
                }
            ]
        raise AssertionError(path)

    monkeypatch.setattr(failed_scheduled_actions, "paginate", fake_paginate)

    assert failed_scheduled_actions.collect_failed_actions(days=1, token="token") == []
    assert failed_scheduled_actions.collect_failed_actions(days=3, token="token")


def test_format_report_links_failures():
    """Report output includes concise failure details and backlinks."""
    report = failed_scheduled_actions.format_report(
        [
            {
                "repo": "ultralytics/private-repo",
                "repo_url": "https://github.com/ultralytics/private-repo",
                "visibility": "private",
                "workflow": "Nightly",
                "event": "push",
                "branch": "main",
                "run_number": 7,
                "failed_at": "2026-06-30T01:02:03Z",
                "sha": "abcdef1",
                "title": "Nightly",
                "url": "https://github.com/ultralytics/private-repo/actions/runs/7",
            }
        ]
    )

    assert "# Failed Default Branch Actions" in report
    assert "**1 failing default-branch workflow run** across **1 repository**." in report
    assert "**By Event:** `push` 1" in report
    assert "## 📦 [private-repo](https://github.com/ultralytics/private-repo)" in report
    assert "failed run" not in report
    assert "(private)" not in report
    assert "**Nightly** (`push`) on `main` failed at 2026-06-30 01:02:03 UTC" in report
    assert "[Run #7](https://github.com/ultralytics/private-repo/actions/runs/7)" in report


def test_format_pr_report_lists_open_prs(monkeypatch):
    """The PR report includes age phases and short linked repository headings."""
    monkeypatch.setattr(github_report, "get_age_days", lambda created_at: 8)
    report = github_report.format_pr_report(
        [
            {
                "repository": {"name": "private-repo"},
                "number": 9,
                "title": "Bump actions/cache in /.github/workflows/ci.yml",
                "url": "https://github.com/ultralytics/private-repo/pull/9",
                "createdAt": "2026-06-30T01:02:03Z",
            }
        ],
        {"private-repo": "https://github.com/ultralytics/private-repo"},
        "all",
    )

    assert "# 🔍 Open Pull Requests - Ultralytics Organization" in report
    assert "**Total:** 1 open PRs across 1/1 all repos" in report
    assert "**By Phase:** 🆕 0 New | 🟢 0 ≤7d | 🟡 1 ≤30d | 🔴 0 >30d" in report
    assert "## 📦 [private-repo](https://github.com/ultralytics/private-repo) - 1 open PR" in report
    assert "[#9](https://github.com/ultralytics/private-repo/pull/9)" in report


def test_collect_repos_filters_single_visibility(monkeypatch):
    """A single visibility input should not include other accessible repository types."""
    monkeypatch.setattr(
        github_report,
        "gh_json",
        lambda args: [
            {
                "name": "public-repo",
                "url": "https://github.com/ultralytics/public-repo",
                "visibility": "public",
                "isArchived": False,
            },
            {
                "name": "private-repo",
                "url": "https://github.com/ultralytics/private-repo",
                "visibility": "private",
                "isArchived": False,
            },
            {
                "name": "archived-repo",
                "url": "https://github.com/ultralytics/archived-repo",
                "visibility": "public",
                "isArchived": True,
            },
        ],
    )

    repos, visibility = github_report.collect_repos("ultralytics", "public", "public")

    assert visibility == "public"
    assert repos == {"public-repo": "https://github.com/ultralytics/public-repo"}


def test_github_report_runs_enabled_sections(monkeypatch):
    """The shared report driver runs PR and failed Actions sections by default."""
    calls = []
    monkeypatch.setattr(github_report, "run_pr_report", lambda: calls.append("prs"))
    monkeypatch.setattr(github_report.failed_scheduled_actions, "run", lambda: calls.append("actions"))

    github_report.run()

    assert calls == ["prs", "actions"]


def test_github_report_keeps_failed_scheduled_actions_alias(monkeypatch):
    """The old failed_scheduled_actions input remains a compatibility alias."""
    calls = []
    monkeypatch.setenv("REPORT_PRS", "false")
    monkeypatch.setenv("REPORT_FAILED_SCHEDULED_ACTIONS", "false")
    monkeypatch.setattr(github_report, "run_pr_report", lambda: calls.append("prs"))
    monkeypatch.setattr(github_report.failed_scheduled_actions, "run", lambda: calls.append("actions"))

    github_report.run()

    assert calls == []


def test_auto_merge_actions_prs_merges_eligible_update(monkeypatch):
    """Eligible GitHub Actions update PRs are merged when checks pass."""
    commands = []

    def fake_run(cmd, capture_output=True, text=True, check=False):
        commands.append(cmd)
        if cmd[:4] == ["gh", "pr", "list", "--repo"]:
            if "app/dependabot" not in cmd:
                return type("Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""})
            return type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": (
                        '[{"number": 9, "title": "Bump actions/cache in /.github/workflows/ci.yml", '
                        '"url": "https://github.com/ultralytics/repo/pull/9", '
                        '"files": [{"path": ".github/workflows/ci.yml"}], '
                        '"mergeable": "MERGEABLE", '
                        '"statusCheckRollup": [{"name": "CI", "conclusion": "SUCCESS"}]}]'
                    ),
                    "stderr": "",
                },
            )
        if cmd[:3] == ["gh", "pr", "merge"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})
        raise AssertionError(cmd)

    monkeypatch.setattr(github_report.subprocess, "run", fake_run)

    report = github_report.auto_merge_actions_prs("ultralytics", {"repo": "https://github.com/ultralytics/repo"})

    assert "- ✅ Merged ultralytics/repo#9" in report
    assert "**Summary:** Found 1 | Merged 1 | Skipped 0" in report
    assert any(command[:3] == ["gh", "pr", "merge"] for command in commands)


def test_auto_merge_actions_prs_skips_without_passing_checks(monkeypatch):
    """Empty, pending, skipped, or neutral status checks should not be auto-merged."""
    commands = []

    def fake_run(cmd, capture_output=True, text=True, check=False):
        commands.append(cmd)
        if cmd[:4] == ["gh", "pr", "list", "--repo"]:
            if "app/dependabot" not in cmd:
                return type("Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""})
            return type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": (
                        '[{"number": 9, "title": "Bump actions/cache in /.github/workflows/ci.yml", '
                        '"url": "https://github.com/ultralytics/repo/pull/9", '
                        '"files": [{"path": ".github/workflows/ci.yml"}], '
                        '"mergeable": "MERGEABLE", "statusCheckRollup": []}, '
                        '{"number": 10, "title": "Bump actions/cache in /.github/workflows/ci.yml", '
                        '"url": "https://github.com/ultralytics/repo/pull/10", '
                        '"files": [{"path": ".github/workflows/ci.yml"}], '
                        '"mergeable": "MERGEABLE", '
                        '"statusCheckRollup": [{"name": "CI", "conclusion": null, "state": "PENDING"}]}, '
                        '{"number": 11, "title": "Bump actions/cache in /.github/workflows/ci.yml", '
                        '"url": "https://github.com/ultralytics/repo/pull/11", '
                        '"files": [{"path": ".github/workflows/ci.yml"}], '
                        '"mergeable": "MERGEABLE", '
                        '"statusCheckRollup": [{"name": "CI", "conclusion": "SKIPPED"}]}, '
                        '{"number": 12, "title": "Bump actions/cache in /.github/workflows/ci.yml", '
                        '"url": "https://github.com/ultralytics/repo/pull/12", '
                        '"files": [{"path": ".github/workflows/ci.yml"}], '
                        '"mergeable": "MERGEABLE", '
                        '"statusCheckRollup": [{"name": "CI", "conclusion": "NEUTRAL"}]}]'
                    ),
                    "stderr": "",
                },
            )
        if cmd[:3] == ["gh", "pr", "merge"]:
            raise AssertionError("Unexpected merge")
        raise AssertionError(cmd)

    monkeypatch.setattr(github_report.subprocess, "run", fake_run)

    report = github_report.auto_merge_actions_prs("ultralytics", {"repo": "https://github.com/ultralytics/repo"})

    assert "- ❌ ultralytics/repo#9: no status checks found" in report
    assert "- ❌ ultralytics/repo#10: checks not passing (CI)" in report
    assert "- ❌ ultralytics/repo#11: checks not passing (CI)" in report
    assert "- ❌ ultralytics/repo#12: checks not passing (CI)" in report
    assert "**Summary:** Found 4 | Merged 0 | Skipped 4" in report
    assert not any(command[:3] == ["gh", "pr", "merge"] for command in commands)


def test_auto_merge_actions_prs_skips_mixed_files(monkeypatch):
    """GitHub Actions update PRs with unrelated files should not be auto-merged."""
    commands = []

    def fake_run(cmd, capture_output=True, text=True, check=False):
        commands.append(cmd)
        if cmd[:4] == ["gh", "pr", "list", "--repo"]:
            if "app/dependabot" not in cmd:
                return type("Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""})
            return type(
                "Result",
                (),
                {
                    "returncode": 0,
                    "stdout": (
                        '[{"number": 9, "title": "Bump actions/cache in /.github/workflows/ci.yml", '
                        '"url": "https://github.com/ultralytics/repo/pull/9", '
                        '"files": [{"path": ".github/workflows/ci.yml"}, {"path": "actions/github_report.py"}], '
                        '"mergeable": "MERGEABLE", '
                        '"statusCheckRollup": [{"name": "CI", "conclusion": "SUCCESS"}]}]'
                    ),
                    "stderr": "",
                },
            )
        if cmd[:3] == ["gh", "pr", "merge"]:
            raise AssertionError("Unexpected merge")
        raise AssertionError(cmd)

    monkeypatch.setattr(github_report.subprocess, "run", fake_run)

    report = github_report.auto_merge_actions_prs("ultralytics", {"repo": "https://github.com/ultralytics/repo"})

    assert "- ❌ ultralytics/repo#9: mixed or non-action files" in report
    assert "**Summary:** Found 1 | Merged 0 | Skipped 1" in report
    assert not any(command[:3] == ["gh", "pr", "merge"] for command in commands)


def test_failed_scheduled_actions_summary_appends_section_break(tmp_path, monkeypatch):
    """Appending after existing summary content should not concatenate Markdown headings."""
    summary = tmp_path / "summary.md"
    summary.write_text("**Summary:** Found 0 | Merged 0 | Skipped 0\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(failed_scheduled_actions, "collect_failed_actions", lambda *args, **kwargs: [])

    failed_scheduled_actions.run()

    assert "Skipped 0\n\n# Failed Default Branch Actions" in summary.read_text()
