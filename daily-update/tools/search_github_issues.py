"""Search authored issues updated on/after a date."""

from __future__ import annotations

from github.GithubException import GithubException
from langchain.tools import tool

from tools.github_client import github_error, github_from_env, json_result


@tool
def search_github_issues(updated_since: str, limit: int = 50) -> str:
    """Search issues authored by the authenticated user, updated on or after a date.

    Args:
        updated_since: ISO date or datetime; the YYYY-MM-DD portion is used.
        limit: Max results to return (default 50).
    """
    client = github_from_env()
    if isinstance(client, dict):
        return json_result(client)

    day = updated_since[:10]
    query = f"author:@me type:issue updated:>={day}"
    try:
        results = client.search_issues(query, sort="updated", order="desc")
        items = []
        for item in results[: min(max(limit, 1), 50)]:
            repo_url = item.repository_url or ""
            items.append(
                {
                    "number": item.number,
                    "title": item.title,
                    "state": item.state,
                    "repository": repo_url.replace("https://api.github.com/repos/", ""),
                    "url": item.html_url,
                    "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
                }
            )
        return json_result(items)
    except GithubException as exc:
        return github_error(exc)
