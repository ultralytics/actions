# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import signal
import time
from unittest.mock import MagicMock

import pytest
import requests

from actions import failure_alert
from actions.utils import Action

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
        f"{API}/runs/7/attempts/1/jobs": {"total_count": len(JOBS), "jobs": JOBS},
        f"{API}/runs/7/attempts/2/jobs": {"total_count": len(JOBS), "jobs": JOBS},
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


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="App child processes run on Unix")
def test_analysis_deadline_posts_bare_alert_and_clears_alarm(alert_env, monkeypatch):
    """A stalled analysis is interrupted before Slack writes and cannot leave an alarm for the next request."""
    monkeypatch.setattr(failure_alert, "get_response", lambda *args, **kwargs: time.sleep(5))
    previous_handler = signal.getsignal(signal.SIGALRM)
    start = time.monotonic()
    failure_alert.run(analysis_timeout=1)
    assert time.monotonic() - start < 3
    assert failure_alert.requests.post.call_args.kwargs["json"] == {"text": "*CI* ❌ `org/repo`"}
    assert signal.getsignal(signal.SIGALRM) == previous_handler and signal.alarm(0) == 0


def test_composite_keeps_immediate_alert_with_ambient_workflow_run(alert_env, monkeypatch):
    """An ambient workflow_run payload must not opt a composite-action caller into App retries."""
    monkeypatch.setattr(failure_alert, "Action", lambda: Action(event_data={"workflow_run": RUN}))
    monkeypatch.setattr(failure_alert, "get_response", lambda *args, **kwargs: "**Transient** - Network failure")
    failure_alert.run()
    assert not requests.Session.post.called
    assert (
        failure_alert.requests.post.call_args.kwargs["json"]["text"]
        == "*CI* ❌ `org/repo`\n*Transient* - Network failure"
    )


@pytest.mark.parametrize("rerun", [False, True])
@pytest.mark.parametrize("verdict", ["Transient", "Bug", "Unclear", ""])
def test_completed_workflow_retries_only_transient_failures(alert_env, monkeypatch, verdict, rerun):
    """Triage controls retries, and only a second failure of the App's own retry alerts, without another retry."""
    event = Action(token="installation-token", event_name="workflow_run", event_data={"workflow_run": RUN})
    monkeypatch.delenv("ALERT_TEXT")
    monkeypatch.delenv("SLACK_WEBHOOK")
    webhook = "https://hooks.slack.com/services/app"
    reply = f"**{verdict}** - Network failure" if verdict else ""
    get_response = MagicMock(return_value=reply)
    monkeypatch.setattr(failure_alert, "get_response", get_response)
    failure_alert.run(event, webhook, rerun=rerun)
    if verdict != "Transient" or not rerun:
        assert not requests.Session.post.called
        assert failure_alert.requests.post.call_args.kwargs["json"]["text"] == (
            f"*CI* ❌ `org/repo`  <{RUN['html_url']}|*Run*>" + (f"\n*{verdict}* - Network failure" if verdict else "")
        )
        return
    assert requests.Session.post.call_args.args[0] == f"{API}/runs/7/rerun-failed-jobs"
    assert not failure_alert.requests.post.called

    for attempt in (  # a passed retry, and a manual rerun that follows an alert, stay silent
        dict(RUN, run_attempt=2, conclusion="success", triggering_actor={"type": "Bot"}),
        dict(RUN, run_attempt=2, triggering_actor={"type": "User"}),
    ):
        event.event_data["workflow_run"] = attempt
        failure_alert.run(event, webhook, rerun=rerun)
    assert not failure_alert.requests.post.called

    event.event_data["workflow_run"] = dict(RUN, run_attempt=2, triggering_actor={"type": "Bot"})
    failure_alert.run(event, webhook, rerun=rerun)
    text = failure_alert.requests.post.call_args.kwargs["json"]["text"]
    assert failure_alert.requests.post.call_args.args[0] == webhook
    assert requests.Session.post.call_args.kwargs["headers"]["Authorization"] == "Bearer installation-token"
    assert "❌" in text and "*Failed on both attempts*: the automatic <" in text and "/attempts/2|rerun>" in text
    prompt = get_response.call_args.args[0][0]["content"]
    assert "Attempt: 2, conclusion: failure" in prompt
    assert "### Log tail: Tests" in prompt
    assert requests.Session.post.call_count == 1
