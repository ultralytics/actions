# Failure Alert Action

Analyze failed workflow logs and post a Slack alert with a **Bug**, **Transient**, or **Unclear** verdict. When called from a completed `workflow_run`, likely transient failures get one automatic failed-jobs rerun before the alert reports the outcome.

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

On the first failed attempt, the existing AI triage decides whether to retry. Only a **Transient** verdict covering every failed job starts a rerun; **Bug**, **Unclear**, missing AI credentials, or failed analysis posts immediately. GitHub's completion event for attempt 2 reports the result, so long-running retries do not hold an idle runner. Successful recovery, repeat failure, and cancellation all report; no attempt starts a second automatic retry.

A manual second attempt also reports its result when the original attempt failed. Reruns of the alert workflow itself stay silent.

Existing `needs`-based alert jobs still post immediately on their first attempt with `actions: read`. Automatic reruns require the separate `workflow_run` workflow above.

## Inputs

| Input               | Description                                                                             | Required | Default                         |
| ------------------- | --------------------------------------------------------------------------------------- | -------- | ------------------------------- |
| `slack_webhook`     | Slack [incoming webhook](https://api.slack.com/messaging/webhooks) URL                  | Yes      | -                               |
| `mention`           | Slack mention to start the alert with                                                   | No       | -                               |
| `openai_api_key`    | OpenAI API key for the failure analysis                                                 | No       | -                               |
| `anthropic_api_key` | Anthropic API key for the failure analysis                                              | No       | -                               |
| `model`             | Model for the failure analysis                                                          | No       | Auto-detected from the API keys |
| `token`             | GitHub token with `actions: write` for retries, otherwise `actions: read` | No       | `${{ github.token }}`           |

## Output

A Slack message names the source workflow and links its run, with ✅ for a passed rerun or ❌ otherwise, followed by the observed rerun result and up to 150 words of triage. Simple failures stay brief; more complex failures can include supporting evidence and next steps, for example:

```text
@ci-team API Canary ✅ org/repo  Run
Rerun result: Passed — Attempt 2
Transient - The original job failed resolving platform.ultralytics.com; the rerun passed.
• The original error was `Temporary failure in name resolution` while fetching `/openapi.json`
```

In Slack, Run, the job names and the source files are links. The triage is also written to the job summary.

## How It Works

1. Lists failed jobs (`failure` or `timed_out`) and their failed steps from the event's attempt. After a passed or cancelled rerun, uses the original failure's logs.
2. Reads log tails before post-job cleanup for up to 10 jobs, sharing a 60,000-character budget with at most 20,000 characters each. Removes timestamps and color codes.
3. Sends the run details and logs to the existing triage model. Unexplained failures must be classified **Unclear**.
4. For an initial **Transient** failure, requests a failed-jobs rerun and leaves reporting to its completion event. Otherwise posts the result and triage as Slack mrkdwn. A rejected retry request posts the original alert with a warning.

## Notes

- **Analysis is optional**: without an API key or usable analysis, the action posts immediately without retrying. A failed package setup posts the bare alert. An unreadable job log is marked unavailable in the triage.
- **Run it after the source completes**: the rerun API requires a completed workflow, and a job's log is only readable once that job ends. Keep the observer timeout short; it does not wait in a polling loop.
- **Data sent to the model**: the failed job log tails go to the chosen AI provider. GitHub masks registered secrets in logs; leave both API keys unset to send the alert without analysis.
