# Ultralytics CLA Action

Checks every pull request commit author against the shared signature ledger in
`ultralytics/cla` and maintains one status comment on the pull request.

```yaml
- uses: ultralytics/actions/cla@main
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    cla-token: ${{ secrets._GITHUB_TOKEN }}
```

The action preserves the existing `signatures/version1/cla.json` schema and
updates its `cla-signatures` branch with optimistic concurrency. Missing or
invalid ledger data, unlinked commit authors, and unsigned contributors fail
the check.

Contributor identity uses GitHub's numeric user ID, so commits from any email
address GitHub associates with the same account require only one signature.
Raw unlinked commit emails are never guessed or treated as identity.

The workflow requires `actions: write` to refresh the PR-head check after a
signature comment and `pull-requests: write` to maintain its single status
comment. It never checks out or executes pull request code.
