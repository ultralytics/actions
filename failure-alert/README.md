# Failure Alert Action

Rerun failed jobs once, then post a Slack alert with the result, with an AI triage of the failed job logs under it: a **Bug**, **Transient** or **Unclear** verdict with what failed and the decisive error, then up to four bullets covering evidence, likely cause, a fix or next diagnostic check, and other distinct failures, linked to the failing jobs and source lines. It works for any repository, language and test framework.

## Usage

Create a separate workflow that observes the completed workflows to watch. GitHub cannot rerun jobs while their original workflow is still running.

```yaml
name: Failure Alert
on:
  workflow_run:
    workflows: [CI] # Workflow names, not filenames
    types: [completed]

permissions:
  actions: write # Read logs and rerun failed jobs

jobs:
  alert:
    if: >-
      github.event.workflow_run.event != 'pull_request' &&
      github.event.workflow_run.run_attempt <= 2 &&
      (github.event.workflow_run.conclusion == 'failure' ||
       github.event.workflow_run.conclusion == 'timed_out' ||
       github.event.workflow_run.run_attempt == 2)
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: ultralytics/actions/failure-alert@main
        with:
          slack_webhook: ${{ secrets.SLACK_WEBHOOK_URL }}
          mention: "<!subteam^S0123456789>" # Optional: Slack user group, <!here> or <@USER_ID>
          openai_api_key: ${{ secrets.OPENAI_API_KEY }} # or anthropic_api_key
```

The workflow must exist on the default branch. Its `if:` decides which source events alert; use `github.event.workflow_run.event` and `head_branch`, not the observer's own event or branch. Remove the old in-workflow alert job to avoid duplicate messages. No checkout of the failed workflow's code is needed.

On the first failed attempt, the action requests a rerun of failed jobs and exits. GitHub's completion event for attempt 2 resumes reporting, so long-running jobs do not consume an idle runner or exceed an alert polling timeout. There is one final Slack message, including successful recovery or cancellation; attempts after 2 and reruns of the alert workflow itself stay silent. A manual rerun that already started is not restarted. A second attempt of an originally successful workflow does not alert.

Existing `needs`-based alert jobs still post immediately on their first attempt with `actions: read`. Automatic reruns require the separate `workflow_run` workflow above.

## Inputs

| Input               | Description                                                                             | Required | Default                         |
| ------------------- | --------------------------------------------------------------------------------------- | -------- | ------------------------------- |
| `slack_webhook`     | Slack [incoming webhook](https://api.slack.com/messaging/webhooks) URL                  | Yes      | -                               |
| `mention`           | Slack mention to start the alert with                                                   | No       | -                               |
| `openai_api_key`    | OpenAI API key for the failure analysis                                                 | No       | -                               |
| `anthropic_api_key` | Anthropic API key for the failure analysis                                              | No       | -                               |
| `model`             | Model for the failure analysis                                                          | No       | Auto-detected from the API keys |
| `token`             | GitHub token with `actions: write` for retries (`actions: read` for in-workflow alerts) | No       | `${{ github.token }}`           |

## Output

A Slack message names the source workflow and links its run, with ✅ for a passed rerun or ❌ otherwise, followed by the observed rerun result and up to 150 words of triage. Simple failures stay brief; more complex failures can include supporting evidence and next steps, for example:

```text
@ci-team CI ❌ org/repo  Run
Bug - Tests (ubuntu-latest, 3.12) fails 4 tests with TypeError: expected str, not NoneType
• The four failures all reach config.py with path=None after the commit made path required
• Update those callers to supply a path, then rerun the affected tests
```

In Slack, Run, the job names and the source files are links. The triage is also written to the job summary.

## How It Works

1. Requests one failed-jobs rerun after the first failed workflow completes; reports on the second completion event. If GitHub rejects the retry request, posts the original failure immediately with a warning.
2. Lists the run's failed jobs (`failure` or `timed_out`) with their failed step, pinned to the event's attempt. A passed or cancelled rerun uses the original failed attempt's logs; a failed rerun uses its own.
3. Reads the end of each failed job's log up to post-job cleanup, where the error usually is, for up to 10 jobs. The jobs share a 60,000-character budget, at most 20,000 each, with timestamps and color codes removed.
4. Sends the run details (workflow, event, branch, commit and job links) and the log tails to the model with a triage prompt that is independent of language and tooling.
5. Posts the alert line and the triage, converted to Slack mrkdwn.

## Notes

- **The result posts even if analysis fails**: without an API key, the action still retries and reports the result without AI analysis. When the run or its job list can't be read, or the model call or uv setup fails, it does the same and logs a warning. A job log that can't be read is marked unavailable, and the analysis uses the rest.
- **Run it after the source completes**: the rerun API requires a completed workflow, and a job's log is only readable once that job ends. Keep the observer timeout short; it does not wait in a polling loop.
- **Data sent to the model**: the failed job log tails go to the chosen AI provider. GitHub masks registered secrets in logs; leave both API keys unset to send the alert without analysis.
