# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

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


def test_collect_failed_actions_latest_run_per_workflow(monkeypatch):
    """Only the latest default-branch run for each workflow should determine whether it is reported."""

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
                    "run_started_at": "2026-06-30T03:00:00Z",
                },
                {
                    "workflow_id": 1,
                    "name": "Nightly",
                    "conclusion": "failure",
                    "run_started_at": "2026-06-29T03:00:00Z",
                },
                {
                    "workflow_id": 2,
                    "name": "Links",
                    "event": "push",
                    "conclusion": "timed_out",
                    "run_started_at": "2026-06-30T04:00:00Z",
                    "run_number": 42,
                    "updated_at": "2026-06-30T04:10:00Z",
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
        visibility="all", repo_visibility="private", token="token"
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
    assert "## 📦 [ultralytics/private-repo](https://github.com/ultralytics/private-repo) - 1 failed run" in report
    assert "(private)" not in report
    assert "**Nightly** (`push`) on `main` failed at 2026-06-30 01:02:03 UTC" in report
    assert "[Run #7](https://github.com/ultralytics/private-repo/actions/runs/7)" in report


def test_github_report_runs_enabled_sections(monkeypatch):
    """The shared report driver gates PR and failed Actions sections by env flags."""
    calls = []
    monkeypatch.setenv("REPORT_PRS", "true")
    monkeypatch.setenv("REPORT_FAILED_ACTIONS", "false")
    monkeypatch.setattr(github_report.scan_prs, "run", lambda: calls.append("prs"))
    monkeypatch.setattr(github_report.failed_scheduled_actions, "run", lambda: calls.append("actions"))

    github_report.run()

    assert calls == ["prs"]


def test_github_report_keeps_failed_scheduled_actions_alias(monkeypatch):
    """The old failed_scheduled_actions input remains a compatibility alias."""
    calls = []
    monkeypatch.setenv("REPORT_PRS", "false")
    monkeypatch.setenv("REPORT_FAILED_SCHEDULED_ACTIONS", "false")
    monkeypatch.setattr(github_report.scan_prs, "run", lambda: calls.append("prs"))
    monkeypatch.setattr(github_report.failed_scheduled_actions, "run", lambda: calls.append("actions"))

    github_report.run()

    assert calls == []


def test_failed_scheduled_actions_summary_appends_section_break(tmp_path, monkeypatch):
    """Appending after the PR section should not concatenate Markdown headings."""
    summary = tmp_path / "summary.md"
    summary.write_text("**Summary:** Found 0 | Merged 0 | Skipped 0\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(failed_scheduled_actions, "collect_failed_actions", lambda *args, **kwargs: [])

    failed_scheduled_actions.run()

    assert "Skipped 0\n\n# Failed Default Branch Actions" in summary.read_text()
