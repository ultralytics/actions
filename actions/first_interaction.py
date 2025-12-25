# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from __future__ import annotations

import os
import time

from . import review_pr
from .summarize_pr import SUMMARY_MARKER
from .utils import (
    ACTIONS_CREDIT,
    Action,
    filter_labels,
    format_skipped_files_dropdown,
    get_pr_open_response,
    get_response,
    remove_html_comments,
)

BLOCK_USER = os.getenv("BLOCK_USER", "false").lower() == "true"
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
        if "Alert" in normalized and not event.is_org_member(username):
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
        pr_number = data["pull_request"]["number"]
        item = event.get_repo_data(f"pulls/{pr_number}")
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


def get_relevant_labels(
    issue_type: str, title: str, body: str, available_labels: dict, current_labels: list
) -> list[str]:
    """Determines relevant labels for GitHub issues/discussions using OpenAI."""
    filtered_labels = filter_labels(available_labels, current_labels, is_pr=(issue_type == "pull request"))
    labels_str = "\n".join(f"- {name}: {description}" for name, description in filtered_labels.items())

    prompt = f"""Select the top 1-3 most relevant labels for the following GitHub {issue_type}.

INSTRUCTIONS:
1. Review the {issue_type} title and description.
2. Consider the available labels and their descriptions.
3. Choose 1-3 labels that best match the {issue_type} content.
4. Only use the "Alert" label when you have high confidence that this is an inappropriate {issue_type}.
5. Respond ONLY with the chosen label names (no descriptions), separated by commas.
6. If no labels are relevant, respond with 'None'.
{'7. Only use the "bug" label if the user provides a clear description of the bug, their environment with relevant package versions and a minimum reproducible example.' if issue_type == "issue" else ""}

AVAILABLE LABELS:
{labels_str}

{issue_type.upper()} TITLE:
{title}

{issue_type.upper()} DESCRIPTION:
{body[:16000]}

YOUR RESPONSE (label names only):
"""
    messages = [
        {
            "role": "system",
            "content": "You are an Ultralytics AI assistant that labels GitHub issues, PRs, and discussions.",
        },
        {"role": "user", "content": prompt},
    ]
    suggested_labels = get_response(messages, temperature=1.0)
    if "none" in suggested_labels.lower():
        return []

    available_labels_lower = {name.lower(): name for name in filtered_labels}
    return [
        available_labels_lower[label.lower().strip()]
        for label in suggested_labels.split(",")
        if label.lower().strip() in available_labels_lower
    ]


def get_first_interaction_response(event, issue_type: str, title: str, body: str, username: str) -> str:
    """Generates a custom LLM response for GitHub issues or discussions (NOT PRs - PRs use unified call)."""
    issue_discussion_response = f"""
👋 Hello @{username}, thank you for submitting a `{event.repository}` 🚀 {issue_type.capitalize()}. To help us address your concern efficiently, please ensure you've provided the following information:

1. For bug reports:
   - A clear and concise description of the bug
   - A minimum reproducible example [MRE](https://docs.ultralytics.com/help/minimum-reproducible-example/) that demonstrates the issue
   - Your environment details (OS, Python version, package versions)
   - Expected behavior vs. actual behavior
   - Any error messages or logs related to the issue

2. For feature requests:
   - A clear and concise description of the proposed feature
   - The problem this feature would solve
   - Any alternative solutions you've considered

3. For questions:
   - Provide as much context as possible about your question
   - Include any research you've already done on the topic
   - Specify which parts of the [documentation](https://docs.ultralytics.com/), if any, you've already consulted

Please make sure you've searched existing {issue_type}s to avoid duplicates. If you need to add any additional information, please comment on this {issue_type}.

Thank you for your contribution to improving our project!
"""

    example = os.getenv("FIRST_ISSUE_RESPONSE") or issue_discussion_response
    org_name, repo_name = event.repository.split("/")

    prompt = f"""Generate a customized response to the new GitHub {issue_type} below:

CONTEXT:
- Repository: {repo_name}
- Organization: {org_name}
- Repository URL: https://github.com/{event.repository}
- User: {username}

INSTRUCTIONS:
- Do not answer the question or resolve the issue directly
- Adapt the example {issue_type} response below as appropriate, keeping all badges, links and references provided
- For bug reports, specifically request a minimum reproducible example (MRE) if not provided
- INCLUDE ALL LINKS AND INSTRUCTIONS IN THE EXAMPLE BELOW, customized as appropriate
- Mention to the user that this is an automated response and that an Ultralytics engineer will also assist soon
- Do not add a sign-off or valediction like "best regards" at the end of your response
- Do not add spaces between bullet points or numbered lists
- Only link to files or URLs in the example below, do not add external links
- Use a few emojis to enliven your response

EXAMPLE {issue_type.upper()} RESPONSE:
{example}

{issue_type.upper()} TITLE:
{title}

{issue_type.upper()} DESCRIPTION:
{body[:16000]}

YOUR {issue_type.upper()} RESPONSE:
"""
    messages = [
        {
            "role": "system",
            "content": f"You are an Ultralytics AI assistant responding to GitHub {issue_type}s for {org_name}.",
        },
        {"role": "user", "content": prompt},
    ]
    return get_response(messages)


def main(*args, **kwargs):
    """Executes auto-labeling and custom response generation for new GitHub issues, PRs, and discussions."""
    event = Action(*args, **kwargs)
    if event.should_skip_openai():
        return

    number, node_id, title, body, username, issue_type, action = get_event_content(event)
    available_labels = event.get_repo_data("labels")
    label_descriptions = {label["name"]: label.get("description") or "" for label in available_labels}

    # Use unified PR open response for new PRs (summary + labels + first comment in 1 API call)
    if issue_type == "pull request" and action == "opened":
        if event.should_skip_pr_author():
            return

        print(f"Processing PR open by @{username} with unified API call...")
        diff = event.get_pr_diff()
        response = get_pr_open_response(event.repository, diff, title, username, label_descriptions)

        if summary := response.get("summary"):
            print("Updating PR description with summary...")
            skipped_dropdown = format_skipped_files_dropdown(response.get("skipped_files", []))
            event.update_pr_description(number, f"{SUMMARY_MARKER}\n\n{ACTIONS_CREDIT}\n\n{summary}{skipped_dropdown}")
        else:
            summary = body

        if relevant_labels := response.get("labels", []):
            apply_and_check_labels(event, number, node_id, issue_type, username, relevant_labels, label_descriptions)

        if first_comment := response.get("first_comment"):
            print("Adding first interaction comment...")
            time.sleep(1)  # sleep to ensure label added first
            event.add_comment(number, node_id, first_comment, issue_type)

        # Automatic PR review after first interaction
        if AUTO_PR_REVIEW:
            print("Starting automatic PR review...")
            review_number = review_pr.dismiss_previous_reviews(event)
            review_data = review_pr.generate_pr_review(event.repository, diff, title, summary)
            review_pr.post_review_summary(event, review_data, review_number)
            print("PR review completed")
        return

    # Handle issues and discussions (NOT PRs)
    current_labels = (
        []
        if issue_type == "discussion"
        else [label["name"].lower() for label in event.get_repo_data(f"issues/{number}/labels")]
    )

    relevant_labels = get_relevant_labels(issue_type, title, body, label_descriptions, current_labels)
    apply_and_check_labels(event, number, node_id, issue_type, username, relevant_labels, label_descriptions)

    if action in {"opened", "created"}:
        custom_response = get_first_interaction_response(event, issue_type, title, body, username)
        event.add_comment(number, node_id, custom_response, issue_type)


if __name__ == "__main__":
    main()
