"""Search Linear comments authored by the authenticated user."""

from __future__ import annotations

from langchain.tools import tool

from tools.clients.linear import json_result, linear_graphql


@tool
def search_linear_comments(user_id: str, since: str, limit: int = 50) -> str:
    """Search Linear comments authored by a user id (from get_linear_user).

    Args:
        user_id: Linear user id from get_linear_user.
        since: ISO-8601 lower bound, e.g. 2026-08-05T14:00:00Z.
        limit: Max comments to return (default 50).
    """
    first = min(max(limit, 1), 50)
    result = linear_graphql(
        """
        query SearchMyLinearComments(
          $userId: ID!
          $since: DateTimeOrDuration!
          $first: Int!
        ) {
          comments(
            first: $first
            orderBy: createdAt
            filter: {
              createdAt: { gte: $since }
              user: { id: { eq: $userId } }
            }
          ) {
            nodes {
              id
              body
              createdAt
              url
              issue {
                identifier
                title
                url
                team { name key }
              }
            }
          }
        }
        """,
        {"userId": user_id, "since": since, "first": first},
    )
    if "error" in result:
        return json_result(result)

    comments = []
    for comment in result["data"]["comments"]["nodes"]:
        issue = comment.get("issue")
        issue_summary = None
        if issue:
            team = issue.get("team") or {}
            team_label = None
            if team.get("key") and team.get("name"):
                team_label = f"{team['key']} ({team['name']})"
            issue_summary = {
                "identifier": issue["identifier"],
                "title": issue["title"],
                "url": issue["url"],
                "team": team_label,
            }
        comments.append(
            {
                "id": comment["id"],
                "body": _truncate(comment.get("body") or "", 400),
                "createdAt": comment["createdAt"],
                "url": comment.get("url"),
                "issue": issue_summary,
            }
        )

    return json_result(comments)


def _truncate(text: str, max_len: int) -> str:
    trimmed = text.strip()
    if len(trimmed) <= max_len:
        return trimmed
    return f"{trimmed[: max_len - 1]}…"
