"""Search authored commits on/after a date (best-effort)."""

from __future__ import annotations

from github.GithubException import GithubException
from langchain.tools import tool

from tools.github_client import github_error, github_from_env, json_result


@tool
def search_github_commits(committer_since: str, limit: int = 50) -> str:
    """Search commits authored by the authenticated user on or after a date (best-effort).

    Args:
        committer_since: ISO date or datetime; the YYYY-MM-DD portion is used.
        limit: Max results to return (default 50).
    """
    client = github_from_env()
    if isinstance(client, dict):
        return json_result(client)

    day = committer_since[:10]
    query = f"author:@me committer-date:>={day}"
    try:
        results = client.search_commits(query, sort="committer-date", order="desc")
        items = []
        for item in results[: min(max(limit, 1), 50)]:
            message = (item.commit.message or "").split("\n", 1)[0]
            committer = item.commit.committer
            author = item.commit.author
            date = None
            if committer and committer.date:
                date = committer.date.isoformat()
            elif author and author.date:
                date = author.date.isoformat()
            items.append(
                {
                    "sha": item.sha[:7],
                    "message": message,
                    "repository": item.repository.full_name if item.repository else None,
                    "url": item.html_url,
                    "date": date,
                }
            )
        return json_result(items)
    except GithubException as exc:
        return github_error(exc)
