# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from unittest.mock import MagicMock

import pytest
import requests

from actions import failure_alert

API = "https://api.github.com/repos/org/repo/actions"
JOB_URL = "https://github.com/org/repo/actions/runs/7/job/1"
RUN = {
    "jobs_url": f"{API}/runs/7/jobs",
    "head_sha": "abc123",
    "head_commit": {"message": "Fix loader\n\nDetails"},
    "repository": {"html_url": "https://github.com/org/repo"},
    "name": "CI",
    "run_number": 42,
    "event": "push",
    "head_branch": "main",
    "html_url": "https://github.com/org/repo/actions/runs/7",
}
JOBS = [
    {
        "id": 1,
        "name": "Tests",
        "conclusion": "failure",
        "html_url": JOB_URL,
        "steps": [{"name": "Pytest", "conclusion": "failure"}],
    },
    {"id": 2, "name": "Lint", "conclusion": "success", "html_url": "https://github.com/org/repo/actions/runs/7/job/2"},
    {"id": 3, "name": "Alert", "conclusion": None, "html_url": "https://github.com/org/repo/actions/runs/7/job/3"},
]
LOG = (
    "2026-10-08T10:00:00.1234567Z \x1b[31mE   ImportError: cannot import name 'load' → ✅\x1b[0m\n"
    "2026-10-08T10:00:01.1234567Z Post job cleanup.\n"
    "2026-10-08T10:00:02.1234567Z cleanup noise\n"
)


def github_get(url, **kwargs):
    """Serve the run, its jobs and the failed job's log like the GitHub API."""
    json_data = {f"{API}/runs/7": RUN, f"{API}/runs/7/jobs": {"total_count": len(JOBS), "jobs": JOBS}}.get(url)
    response = MagicMock(status_code=200, content=LOG.encode(), **{"elapsed.total_seconds.return_value": 0.1})
    response.json.return_value = json_data
    return response


@pytest.fixture
def alert_env(monkeypatch, tmp_path):
    """Set the environment the failure-alert composite action passes to the module."""
    for name, value in {
        "ALERT_TEXT": "*CI* ❌ `org/repo`",
        "GITHUB_REPOSITORY": "org/repo",
        "GITHUB_RUN_ID": "7",
        "GITHUB_TOKEN": "token",
        "SLACK_WEBHOOK": "https://hooks.slack.com/services/T/B/X",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setattr("actions.utils.openai_utils.OPENAI_API_KEY", "key")  # read at import time
    monkeypatch.setattr("requests.Session.get", MagicMock(side_effect=github_get))
    monkeypatch.setattr(failure_alert.requests, "post", MagicMock())
    return tmp_path / "summary.md"


def test_run_posts_alert_with_triage_of_failed_jobs(alert_env, monkeypatch):
    """The triage prompt holds only failed jobs and their cleaned log tails, and the reply posts as Slack mrkdwn."""
    reply = (
        f"**Bug** - [Tests]({JOB_URL}) fails with `ImportError: cannot import name 'load'`\n"
        "- [loader.py](https://github.com/org/repo/blob/abc123/loader.py#L3) dropped `load` used at <module>"
    )
    get_response = MagicMock(return_value=reply)
    monkeypatch.setattr(failure_alert, "get_response", get_response)
    failure_alert.run()

    (messages,), kwargs = get_response.call_args
    prompt = messages[0]["content"]
    assert [m["role"] for m in messages] == ["user"] and kwargs == {"check_links": False}
    assert "https://github.com/org/repo/blob/abc123/<path>#L<line>" in prompt
    assert "Commit: https://github.com/org/repo/commit/abc123 Fix loader\n" in prompt
    assert f"- Tests (step: Pytest): {JOB_URL}" in prompt and "Lint" not in prompt and "Alert" not in prompt
    assert "### Log tail: Tests\nE   ImportError: cannot import name 'load' → ✅\n" in prompt
    assert "cleanup noise" not in prompt and "\x1b" not in prompt and "10:00:00" not in prompt

    assert failure_alert.requests.post.call_args.kwargs["json"] == {
        "text": f"*CI* ❌ `org/repo`\n*Bug* - <{JOB_URL}|Tests> fails with `ImportError: cannot import name 'load'`\n"
        "• <https://github.com/org/repo/blob/abc123/loader.py#L3|loader.py> dropped `load` used at &lt;module&gt;"
    }
    assert alert_env.read_text() == f"## Failure Analysis\n\n{reply}\n"


def test_run_posts_bare_alert_when_analysis_fails(alert_env, monkeypatch, capsys):
    """An analysis error still posts the alert, without the triage."""
    monkeypatch.setattr(failure_alert, "get_response", MagicMock(side_effect=requests.HTTPError("502 Server Error")))
    failure_alert.run()

    assert failure_alert.requests.post.call_args.kwargs["json"] == {"text": "*CI* ❌ `org/repo`"}
    assert "::warning::Failure analysis skipped: 502 Server Error" in capsys.readouterr().out
    assert not alert_env.exists()
