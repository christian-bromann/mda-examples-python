"""List recent GitHub account events newer than `since`."""

from __future__ import annotations

from typing import Any

from github.GithubException import GithubException
from langchain.tools import tool

from tools.clients.github import github_error, github_from_env, json_result


@tool
def list_github_events(login: str, since: str, limit: int = 80) -> str:
    """List recent GitHub account events for a user login, newer than `since` (ISO-8601).

    Args:
        login: GitHub username from get_github_user.
        since: ISO-8601 lower bound, e.g. 2026-08-05T14:00:00Z.
        limit: Max events to return (default 80, max 100).
    """
    client = github_from_env()
    if isinstance(client, dict):
        return json_result(client)

    max_items = min(max(limit, 1), 100)
    events: list[dict[str, Any]] = []
    page = 1

    try:
        # Authenticated `/users/{username}/events` includes private events the
        # token can see when `login` is the token owner.
        user = client.get_user(login)
        while len(events) < max_items and page <= 3:
            page_events = user.get_events().get_page(page - 1)
            if not page_events:
                break

            for event in page_events:
                created_at = event.created_at.isoformat().replace("+00:00", "Z")
                if created_at < since:
                    return json_result(events[:max_items])
                events.append(
                    {
                        "id": str(event.id),
                        "type": event.type,
                        "created_at": created_at,
                        "repo": event.repo.full_name if event.repo else None,
                        "payload": _summarize_payload(event.type, event.payload),
                    }
                )
                if len(events) >= max_items:
                    break

            if len(page_events) < 30:
                break
            page += 1
    except GithubException as exc:
        return github_error(exc)

    return json_result(events[:max_items])


def _summarize_payload(
    event_type: str | None, payload: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not payload:
        return None
    if event_type == "PushEvent":
        commits = payload.get("commits") or []
        return {
            "ref": payload.get("ref"),
            "size": payload.get("size"),
            "commits": [
                {
                    "sha": (c.get("sha") or "")[:7],
                    "message": c.get("message"),
                }
                for c in commits[:5]
                if isinstance(c, dict)
            ],
        }
    if event_type in {
        "PullRequestEvent",
        "PullRequestReviewEvent",
        "PullRequestReviewCommentEvent",
    }:
        pr = payload.get("pull_request") or {}
        return {
            "action": payload.get("action"),
            "number": pr.get("number"),
            "title": pr.get("title"),
            "url": pr.get("html_url"),
        }
    if event_type in {"IssuesEvent", "IssueCommentEvent"}:
        issue = payload.get("issue") or {}
        return {
            "action": payload.get("action"),
            "number": issue.get("number"),
            "title": issue.get("title"),
            "url": issue.get("html_url"),
        }
    if event_type in {"CreateEvent", "DeleteEvent"}:
        return {"ref_type": payload.get("ref_type"), "ref": payload.get("ref")}
    return {"action": payload.get("action")}
