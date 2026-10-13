# Failure Alert Action

Post a Slack alert when a workflow run fails, with an AI triage of the failed job logs under it: a **Bug**, **Transient** or **Unclear** verdict with what failed and the decisive error, then up to four bullets covering evidence, likely cause, a fix or next diagnostic check, and other distinct failures, linked to the failing jobs and source lines. It works for any repository, language and test framework.

## GitHub App integration

Ultralytics repositories can opt in centrally through `FAILURE_ALERTS` in the [GitHub App](https://github.com/ultralytics/assistant/blob/main/assistant/google/cloud/run/actions/main.py). Each entry selects the repository, stable workflow ID, source events, Slack destination, and mention. No observer workflow or notification job is needed in the watched repository; changing the workflow's display name does not affect its opt-in.

The App passes the completed `workflow_run` and its installation token to this same module. Only an initial **Transient** verdict covering every failed job requests one failed-jobs rerun. **Bug**, **Unclear**, missing AI credentials, or failed analysis posts immediately. Attempt 2's completion reports recovery, repeat failure, or cancellation; no further automatic retry is started. A manual second attempt also reports if the original attempt failed. Successful or cancelled reruns use the original failure's logs, and a rejected retry request posts an alert immediately.

The App needs `Actions: write`, a `workflow_run` webhook subscription, and the configured Slack webhooks. See the [App deployment instructions](https://github.com/ultralytics/assistant/blob/main/assistant/google/cloud/run/README.md#github-app-failure-alerts). Remove existing failure notifications when enabling this integration to avoid duplicates. Release announcements and other intentional Slack messages stay in their owners.

## Composite action usage

Add a job that `needs` the jobs to watch and runs only when one of them fails:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: make test

  alert:
    needs: [test]
    if: always() && contains(needs.*.result, 'failure') && github.event_name != 'pull_request' && github.run_attempt == '1'
    runs-on: ubuntu-latest
    permissions:
      actions: read # read the failed job logs
    steps:
      - uses: ultralytics/actions/failure-alert@main
        with:
          slack_webhook: ${{ secrets.SLACK_WEBHOOK_URL }}
          mention: "<!subteam^S0123456789>" # Optional: Slack user group, <!here> or <@USER_ID>
          openai_api_key: ${{ secrets.OPENAI_API_KEY }} # or anthropic_api_key
```

The job's `if:` decides which events and branches alert. The action only posts on the first run attempt; re-runs stay silent.

## Inputs

| Input               | Description                                                            | Required | Default                         |
| ------------------- | ---------------------------------------------------------------------- | -------- | ------------------------------- |
| `slack_webhook`     | Slack [incoming webhook](https://api.slack.com/messaging/webhooks) URL | Yes      | -                               |
| `mention`           | Slack mention to start the alert with                                  | No       | -                               |
| `openai_api_key`    | OpenAI API key for the failure analysis                                | No       | -                               |
| `anthropic_api_key` | Anthropic API key for the failure analysis                             | No       | -                               |
| `model`             | Model for the failure analysis                                         | No       | Auto-detected from the API keys |
| `token`             | GitHub token that can read the run's job logs (`actions: read`)        | No       | `${{ github.token }}`           |

## Output

A Slack message that keeps the usual one-line alert, with ❌ as its only emoji, followed by up to 150 words of triage. Simple failures stay brief; more complex failures can include supporting evidence and next steps, for example:

```text
@ci-team CI ❌ org/repo  Run
Bug - Tests (ubuntu-latest, 3.12) fails 4 tests with TypeError: expected str, not NoneType
• The four failures all reach config.py with path=None after the commit made path required
• Update those callers to supply a path, then rerun the affected tests
```

In Slack, Run, the job names and the source files are links. The triage is also written to the job summary.

## How It Works

1. Lists the run's failed jobs (`failure` or `timed_out`) with their failed step.
2. Reads the end of each failed job's log up to post-job cleanup, where the error usually is, for up to 10 jobs. The jobs share a 60,000-character budget, at most 20,000 each, with timestamps and color codes removed.
3. Sends the run details (workflow, event, branch, commit and job links) and the log tails to the model with a triage prompt that is independent of language and tooling.
4. Posts the alert line and the triage, converted to Slack mrkdwn.

## Notes

- **On the first attempt, the alert posts even if analysis fails**: without an API key, the action skips the analysis and posts the alert line alone. When the run or its job list can't be read, or the model call or uv setup fails, it does the same and logs a warning. A job log that can't be read is marked unavailable, and the analysis uses the rest.
- **Run it in its own job**: a job's log is only readable once the job ends, so a `failure()` step inside the failing job cannot analyze that job.
- **Data sent to the model**: the failed job log tails go to the chosen AI provider. GitHub masks registered secrets in logs; leave both API keys unset to send the alert without analysis.
