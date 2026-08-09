# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import os

from . import review_pr
from .summarize_pr import SUMMARY_MARKER
from .utils import (
    ACTIONS_CREDIT,
    GITHUB_API_URL,
    Action,
    filter_labels,
    format_skipped_files_dropdown,
    get_pr_open_response,
    get_response,
    remove_html_comments,
)

BLOCK_USER = os.getenv("BLOCK_USER", "false").lower() == "true"
AUTO_LABELS = os.getenv("LABELS", "true").lower() == "true"
AUTO_PR_SUMMARY = os.getenv("SUMMARY", "true").lower() == "true"
AUTO_PR_REVIEW = os.getenv("REVIEW", "true").lower() == "true"


def apply_and_check_labels(event, number, node_id, issue_type, username, labels, label_descriptions):
    """Normalizes, applies labels, and handles Alert label if present."""
    if not labels:
        print("No relevant labels found or applied.")
        return

    available = {k.lower(): k for k in label_descriptions}
    if normalized := [available.get(label.lower(), label) for label in labels if label.lower() in available]:
        print(f"Applying labels: {normalized}")
        event.apply_labels(number, node_id, normalized, issue_type)
        if any(label.lower() == "alert" for label in normalized) and not event.is_org_member(username):
            event.handle_alert(number, node_id, issue_type, username, block=BLOCK_USER)


def get_event_content(event) -> tuple[int, str, str, str, str, str, str]:
    """Extracts key information from GitHub event data for issues, pull requests, or discussions."""
    data = event.event_data
    name = event.event_name
    action = data["action"]
    if name == "issues":
        item = data["issue"]
        issue_type = "issue"
    elif name in ["pull_request", "pull_request_target"]:
        item = data["pull_request"]
        issue_type = "pull request"
    elif name == "discussion":
        item = data["discussion"]
        issue_type = "discussion"
    else:
        raise ValueError(f"Unsupported event type: {name}")

    number = item["number"]
    node_id = item.get("node_id") or item.get("id")
    title = item["title"]
    body = remove_html_comments(item.get("body") or "")
    username = item["user"]["login"]
    return number, node_id, title, body, username, issue_type, action


def get_first_interaction_response(
    event,
    issue_type: str,
    title: str,
    body: str,
    username: str,
    available_labels: dict,
    current_labels: list,
    repository_context: str,
) -> dict:
    """Generate labels and a first response for an issue or discussion in one LLM call."""
    issue_discussion_response = f"""
👋 Thanks @{username} for opening this `{event.repository}` {issue_type}. This is an automated first response; an Ultralytics engineer will assist soon.
"""

    configured_example = os.getenv("FIRST_ISSUE_RESPONSE")
    example = configured_example or issue_discussion_response
    org_name, repo_name = event.repository.split("/")
    filtered_labels = filter_labels(available_labels, current_labels)
    labels_str = "\n".join(f"- {name}: {description}" for name, description in filtered_labels.items())

    prompt = f"""Process the new GitHub {issue_type} below and return labels plus a first response.

CONTEXT:
- Repository: {repo_name}
- Organization: {org_name}
- Repository metadata: {repository_context or "No additional metadata provided."}
- User: {username}

LABELS:
- Select 0-3 labels only from the available names below; descriptions are authoritative
- Use Alert only with high confidence for spam, abuse, or illegal content
- Use bug only when the report describes concrete incorrect behavior with enough evidence to investigate; do not require a particular language, package manager, or reproduction format
- Do not repeat a current label or guess from the repository name alone

AVAILABLE LABELS:
{labels_str}

FIRST RESPONSE:
- Acknowledge the concrete request or failure in the opening sentence without merely restating the title
- Ask only for specific information that is materially missing; do not repeat a generic checklist or request details already supplied
- For bugs, missing evidence may include minimal reproduction steps, observed and expected behavior, relevant environment/toolchain/dependency versions, and focused logs
- For feature requests, ask at most one question that would materially change scope or behavior
- Do not diagnose a cause or claim a resolution without evidence
- Stay repository- and technology-aware; never assume Python, pip, PyPI, a branch name, or a release process
- State that this is automated and an Ultralytics engineer will assist soon
- {"Use the configured example as authoritative repository guidance; retain only instructions and links relevant to this report, and condense repetition" if configured_example else "Use at most 140 words"}
- Do not add a heading, sign-off, or external links not present in the configured example

EXAMPLE {issue_type.upper()} RESPONSE:
{example}

{issue_type.upper()} TITLE:
{title}

{issue_type.upper()} DESCRIPTION:
{body[:16000]}

Return the labels and final comment only.
"""
    messages = [
        {
            "role": "system",
            "content": f"You are an Ultralytics AI assistant responding to GitHub {issue_type}s for {org_name}.",
        },
        {"role": "user", "content": prompt},
    ]
    schema = {
        "type": "object",
        "properties": {
            "labels": {"type": "array", "items": {"type": "string"}},
            "first_comment": {"type": "string"},
        },
        "required": ["labels", "first_comment"],
        "additionalProperties": False,
    }
    response = get_response(
        messages,
        text_format={"format": {"type": "json_schema", "name": "first_interaction", "strict": True, "schema": schema}},
    )
    available = {name.lower(): name for name in filtered_labels}
    response["labels"] = [
        available[label.lower()] for label in response.get("labels", []) if label.lower() in available
    ]
    return response


def main(*args, **kwargs):
    """Executes auto-labeling and custom response generation for new GitHub issues, PRs, and discussions."""
    event = Action(*args, **kwargs)
    if event.should_skip_llm():
        return

    number, node_id, title, body, username, issue_type, action = get_event_content(event)
    if issue_type == "pull request" and action == "opened" and event.should_skip_pr_author():
        return
    if issue_type != "pull request" and action not in {"opened", "created"}:
        return

    available_labels = (
        event.paginate(f"{GITHUB_API_URL}/repos/{event.repository}/labels", hard=True) if AUTO_LABELS else []
    )
    label_descriptions = {label["name"]: label.get("description") or "" for label in available_labels}
    repository_data = event.event_data.get("repository", {})
    repository_context = "; ".join(
        str(value)
        for value in (
            repository_data.get("description"),
            f"primary language: {repository_data['language']}" if repository_data.get("language") else None,
            f"default branch: {repository_data['default_branch']}" if repository_data.get("default_branch") else None,
        )
        if value
    )

    # Use unified PR open response for new PRs (summary + labels + first comment in 1 API call)
    if issue_type == "pull request" and action == "opened":
        if AUTO_PR_SUMMARY or AUTO_LABELS:
            print(f"Processing PR open by @{username} with unified API call...")
            diff = event.get_pr_diff()
            response = get_pr_open_response(
                event.repository,
                diff,
                title,
                username,
                label_descriptions,
                body,
                repository_context,
                summarize=AUTO_PR_SUMMARY,
                acknowledge=AUTO_LABELS,
                current_labels=[label["name"] for label in event.pr.get("labels", [])],
            )

            if AUTO_PR_SUMMARY and (summary := response.get("summary")):
                print("Updating PR description with summary...")
                skipped_dropdown = format_skipped_files_dropdown(response.get("skipped_files", []))
                event.update_pr_description(
                    number,
                    f"{SUMMARY_MARKER}\n\n{ACTIONS_CREDIT}\n\n{summary}{skipped_dropdown}",
                )
                if sum(not char.isspace() for char in body) < 30:
                    body = f"{body.rstrip()}\n\n{summary}".lstrip()

            if AUTO_LABELS:
                apply_and_check_labels(
                    event,
                    number,
                    node_id,
                    issue_type,
                    username,
                    response.get("labels", []),
                    label_descriptions,
                )
                if first_comment := response.get("first_comment"):
                    print("Adding first interaction comment...")
                    event.add_comment(number, node_id, first_comment, issue_type)

        # Automatic PR review after first interaction
        if AUTO_PR_REVIEW:
            print("Starting automatic PR review...")
            review_pr.run_review(event, title, body)
        return

    # Handle issues and discussions (NOT PRs)
    item = event.event_data.get("issue", {}) if issue_type == "issue" else {}
    current_labels = [label["name"].lower() for label in item.get("labels", [])]
    response = get_first_interaction_response(
        event, issue_type, title, body, username, label_descriptions, current_labels, repository_context
    )
    apply_and_check_labels(event, number, node_id, issue_type, username, response.get("labels", []), label_descriptions)
    if custom_response := response.get("first_comment"):
        event.add_comment(number, node_id, custom_response, issue_type)


if __name__ == "__main__":
    main()
