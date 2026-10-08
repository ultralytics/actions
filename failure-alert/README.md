# Failure Alert Action

Post a Slack alert when a workflow run fails, with an AI triage of the failed job logs: a **Bug**, **Transient** or **Unclear** verdict followed by up to three bullets on what failed, the decisive error and its likely cause, linked to the failing jobs and source lines. It works for any repository, language and test framework.

## Usage

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

The job's `if:` decides when to alert, such as which events, branches or run attempts. The action posts every time it runs.

## Inputs

| Input               | Description                                                            | Required | Default                           |
| ------------------- | ---------------------------------------------------------------------- | -------- | --------------------------------- |
| `slack_webhook`     | Slack [incoming webhook](https://api.slack.com/messaging/webhooks) URL | Yes      | -                                 |
| `mention`           | Slack mention to start the alert with                                  | No       | -                                 |
| `message`           | Slack mrkdwn alert line                                                | No       | Workflow, repository and run link |
| `openai_api_key`    | OpenAI API key for the failure analysis                                | No       | -                                 |
| `anthropic_api_key` | Anthropic API key for the failure analysis                             | No       | -                                 |
| `model`             | Model for the failure analysis                                         | No       | Auto-detected from the API keys   |
| `token`             | GitHub token that can read the run's job logs (`actions: read`)        | No       | `${{ github.token }}`             |

## Output

A Slack message with the alert line and the triage, for example:

```text
@ci-team CI ❌ org/repo  Run
Verdict: Bug - parse_config no longer accepts None
• Tests (ubuntu-latest, 3.12): 4 tests in tests/test_config.py fail with TypeError: expected str, not NoneType
• Likely cause: the commit made path required in config.py without updating its callers
```

Job and source line names link to GitHub in Slack. The triage is also written to the job summary.

## How It Works

1. Lists the run's failed jobs (`failure` or `timed_out`) with their failed step.
2. Reads the end of each failed job's log up to post-job cleanup, where the error usually is, for up to 10 jobs. The jobs share a 60,000-character budget, at most 20,000 each, with timestamps and color codes removed.
3. Sends the run details (workflow, event, branch, commit and job links) and the log tails to the model with a triage prompt that is independent of language and tooling.
4. Posts the alert line and the triage, converted to Slack mrkdwn.

## Notes

- **The alert always posts**: without an API key, or when log reading, the model call or the uv setup fails, the action posts the alert line alone and logs a warning.
- **Run it in its own job**: a job's log is only readable once the job ends, so a `failure()` step inside the failing job cannot analyze that job.
- **Data sent to the model**: the failed job log tails go to the chosen AI provider. GitHub masks registered secrets in logs; leave both API keys unset to send the alert without analysis.
