# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import json
from unittest.mock import MagicMock

import pytest
import requests

from actions import failure_alert

API = "https://api.github.com/repos/org/repo/actions"
JOB_URL = "https://github.com/org/repo/actions/runs/7/job/1"
RUN = {
    "id": 7,
    "url": f"{API}/runs/7",
    "run_attempt": 1,
    "status": "completed",
    "conclusion": "failure",
    "head_sha": "abc123",
    "head_commit": {"message": "Fix loader\n\nDetails"},
    "repository": {"html_url": "https://github.com/org/repo", "full_name": "org/repo"},
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
    json_data = {
        f"{API}/runs/7": RUN,
        f"{API}/runs/7/attempts/1": RUN,
        f"{API}/runs/7/attempts/1/jobs": {"total_count": len(JOBS), "jobs": JOBS},
        f"{API}/runs/7/attempts/2/jobs": {"total_count": 1, "jobs": [dict(JOBS[0], name="Retried tests")]},
    }.get(url)
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
    monkeypatch.setattr("requests.Session.post", MagicMock(return_value=github_get("retry")))
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


@pytest.mark.parametrize("conclusion", ["success", "failure", "timed_out", "cancelled"])
@pytest.mark.parametrize("ai", [True, False])
def test_completed_workflow_retries_once_then_reports_result(alert_env, monkeypatch, conclusion, ai):
    """A completed failure defers Slack until the rerun event and analyzes the correct attempt's real log path."""
    event_path = alert_env.parent / "event.json"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    event_path.write_text(json.dumps({"workflow_run": RUN}))
    monkeypatch.setattr("actions.utils.openai_utils.OPENAI_API_KEY", "key" if ai else "")
    monkeypatch.setattr("actions.utils.openai_utils.ANTHROPIC_API_KEY", "")
    get_response = MagicMock(return_value="**Transient** - Network failure")
    monkeypatch.setattr(failure_alert, "get_response", get_response)
    failure_alert.run()
    assert requests.Session.post.call_args.args[0] == f"{API}/runs/7/rerun-failed-jobs"
    assert not failure_alert.requests.post.called and not get_response.called

    event_path.write_text(json.dumps({"workflow_run": dict(RUN, run_attempt=2, conclusion=conclusion)}))
    failure_alert.run()
    text = failure_alert.requests.post.call_args.kwargs["json"]["text"]
    assert f"Rerun result: {'Passed' if conclusion == 'success' else conclusion}" in text
    assert "/attempts/2|Attempt 2>" in text and ("*Transient* - Network failure" in text) == ai
    if ai:
        prompt = get_response.call_args.args[0][0]["content"]
        expected_attempt = 2 if conclusion in {"failure", "timed_out"} else 1
        assert f"logs from attempt {expected_attempt}" in prompt
        assert ("Retried tests" in prompt) == (expected_attempt == 2)
    assert requests.Session.post.call_count == 1

    event_path.write_text(json.dumps({"workflow_run": dict(RUN, run_attempt=3, conclusion=conclusion)}))
    failure_alert.run()
    assert requests.Session.post.call_count == 1 and failure_alert.requests.post.call_count == 1


def test_retry_failure_still_alerts_without_ai(alert_env, monkeypatch):
    """A denied rerun cannot suppress the original alert, including when no AI credentials are configured."""
    event_path = alert_env.parent / "event.json"
    event_path.write_text(json.dumps({"workflow_run": RUN}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setattr("actions.utils.openai_utils.OPENAI_API_KEY", "")
    monkeypatch.setattr("actions.utils.openai_utils.ANTHROPIC_API_KEY", "")
    requests.Session.post.return_value.status_code = 403
    requests.Session.post.return_value.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    failure_alert.run()
    assert failure_alert.requests.post.call_args.kwargs["json"]["text"] == (
        "*CI* ❌ `org/repo`\nAutomatic rerun could not be confirmed; check the linked run."
    )


@pytest.mark.parametrize("attempt,conclusion", [(1, "success"), (1, "cancelled"), (2, "success")])
def test_successful_original_workflow_stays_silent(alert_env, monkeypatch, attempt, conclusion):
    """An initially successful workflow and its manual rerun do not produce failure alerts or another rerun."""
    event_path = alert_env.parent / "event.json"
    event_path.write_text(json.dumps({"workflow_run": dict(RUN, run_attempt=attempt, conclusion=conclusion)}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setitem(RUN, "conclusion", "success")
    failure_alert.run()
    assert not requests.Session.post.called and not failure_alert.requests.post.called
