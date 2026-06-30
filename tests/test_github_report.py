# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from actions import failed_scheduled_actions, github_report


def test_collect_failed_scheduled_actions_latest_run_per_workflow(monkeypatch):
    """Only the latest scheduled run for each workflow should determine whether it is reported."""

    def fake_paginate(path, params=None, key=None, max_pages=100, token=None):
        if path == "/orgs/ultralytics/repos":
            return [
                {
                    "full_name": "ultralytics/private-repo",
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
                    "conclusion": "failure",
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

    failures = failed_scheduled_actions.collect_failed_scheduled_actions(
        visibility="all", repo_visibility="private", token="token"
    )

    assert len(failures) == 1
    assert failures[0]["repo"] == "ultralytics/private-repo"
    assert failures[0]["workflow"] == "Links"
    assert failures[0]["sha"] == "abcdef1"


def test_format_report_links_failures():
    """Report output includes concise failure details and backlinks."""
    report = failed_scheduled_actions.format_report(
        [
            {
                "repo": "ultralytics/private-repo",
                "visibility": "private",
                "workflow": "Nightly",
                "branch": "main",
                "run_number": 7,
                "failed_at": "2026-06-30T01:02:03Z",
                "sha": "abcdef1",
                "title": "Nightly",
                "url": "https://github.com/ultralytics/private-repo/actions/runs/7",
            }
        ]
    )

    assert "# Failed Scheduled Actions" in report
    assert "**Nightly** on `main` failed at 2026-06-30 01:02:03 UTC" in report
    assert "[Run #7](https://github.com/ultralytics/private-repo/actions/runs/7)" in report


def test_github_report_runs_enabled_sections(monkeypatch):
    """The shared report driver gates PR and failed scheduled Actions sections by env flags."""
    calls = []
    monkeypatch.setenv("REPORT_PRS", "true")
    monkeypatch.setenv("REPORT_FAILED_SCHEDULED_ACTIONS", "false")
    monkeypatch.setattr(github_report.scan_prs, "run", lambda: calls.append("prs"))
    monkeypatch.setattr(github_report.failed_scheduled_actions, "run", lambda: calls.append("actions"))

    github_report.run()

    assert calls == ["prs"]
