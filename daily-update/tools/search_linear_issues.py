"""Search Linear issues assigned to or created by the authenticated user."""

from __future__ import annotations

from typing import Any, Literal

from langchain.tools import tool

from tools.clients.linear import json_result, linear_graphql

Role = Literal["assignee", "creator"]


@tool
def search_linear_issues(since: str, limit: int = 50) -> str:
    """Search Linear issues assigned to or created by the authenticated user.

    Args:
        since: ISO-8601 lower bound, e.g. 2026-08-05T14:00:00Z.
        limit: Max issues to return (default 50).
    """
    first = min(max(limit, 1), 50)
    result = linear_graphql(
        """
        query SearchMyLinearIssues($since: DateTimeOrDuration!, $first: Int!) {
          viewer {
            id
            assignedIssues(
              first: $first
              orderBy: updatedAt
              filter: { updatedAt: { gte: $since } }
            ) {
              nodes {
                id
                identifier
                title
                url
                priority
                updatedAt
                completedAt
                createdAt
                state { name type }
                team { name key }
                project { name }
                assignee { id name }
                creator { id name }
              }
            }
            createdIssues(
              first: $first
              orderBy: updatedAt
              filter: { updatedAt: { gte: $since } }
            ) {
              nodes {
                id
                identifier
                title
                url
                priority
                updatedAt
                completedAt
                createdAt
                state { name type }
                team { name key }
                project { name }
                assignee { id name }
                creator { id name }
              }
            }
          }
        }
        """,
        {"since": since, "first": first},
    )
    if "error" in result:
        return json_result(result)

    viewer = result["data"]["viewer"]
    viewer_id = viewer["id"]
    by_id: dict[str, dict[str, Any]] = {}

    for issue in viewer["assignedIssues"]["nodes"]:
        by_id[issue["id"]] = _summarize_issue(issue, viewer_id, "assignee")
    for issue in viewer["createdIssues"]["nodes"]:
        existing = by_id.get(issue["id"])
        if existing:
            roles = set(existing["roles"])
            roles.add("creator")
            existing["roles"] = sorted(roles)
        else:
            by_id[issue["id"]] = _summarize_issue(issue, viewer_id, "creator")

    issues = sorted(by_id.values(), key=lambda item: item["updatedAt"], reverse=True)
    return json_result(issues[:first])


def _summarize_issue(
    issue: dict[str, Any],
    viewer_id: str,
    role: Role,
) -> dict[str, Any]:
    roles: set[Role] = {role}
    assignee = issue.get("assignee") or {}
    creator = issue.get("creator") or {}
    if assignee.get("id") == viewer_id:
        roles.add("assignee")
    if creator.get("id") == viewer_id:
        roles.add("creator")

    state = issue.get("state") or {}
    team = issue.get("team") or {}
    project = issue.get("project") or {}

    team_label = None
    if team.get("key") and team.get("name"):
        team_label = f"{team['key']} ({team['name']})"

    return {
        "id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
        "url": issue["url"],
        "priority": issue["priority"],
        "state": state.get("name"),
        "stateType": state.get("type"),
        "team": team_label,
        "project": project.get("name"),
        "roles": sorted(roles),
        "updatedAt": issue["updatedAt"],
        "completedAt": issue.get("completedAt"),
        "createdAt": issue["createdAt"],
    }
