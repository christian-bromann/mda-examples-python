"""Search recent public X posts (optional; needs X_BEARER_TOKEN)."""

from __future__ import annotations

from typing import Any

from langchain.tools import tool

from tools.json_result import json_result
from tools.x_client import x_bearer_or_skip, x_error, x_get


@tool
def search_x_posts(query: str, max_results: int = 25) -> str:
    """Search recent public X posts for focus.md niches.

    For daily zeitgeist scans use max_results ~25-50 and several queries so you
    see volume, not a skim.

    Args:
        query: X recent-search query, e.g.
            '("deep agents" OR langgraph) -is:retweet lang:en'.
        max_results: Max posts to return (default 25, capped at 50).
    """
    token = x_bearer_or_skip()
    if isinstance(token, dict):
        return json_result(token)

    limit = min(max(max_results, 1), 50)
    api_max = max(10, min(limit, 100))
    try:
        payload = x_get(
            "/tweets/search/recent",
            {
                "query": query,
                "max_results": str(api_max),
                "tweet.fields": "created_at,public_metrics,lang,author_id",
                "expansions": "author_id",
                "user.fields": "username,name",
            },
            token,
        )
    except RuntimeError as exc:
        return x_error(exc)

    users: dict[str, dict[str, Any]] = {
        user["id"]: user for user in (payload.get("includes") or {}).get("users") or []
    }

    posts = []
    for tweet in (payload.get("data") or [])[:limit]:
        author_id = tweet.get("author_id")
        author = users.get(author_id) if author_id else None
        username = author.get("username") if author else None
        posts.append(
            {
                "id": tweet.get("id"),
                "text": tweet.get("text"),
                "createdAt": tweet.get("created_at"),
                "lang": tweet.get("lang"),
                "metrics": tweet.get("public_metrics"),
                "author": (
                    {
                        "id": author["id"],
                        "username": author.get("username"),
                        "name": author.get("name"),
                    }
                    if author
                    else {"id": author_id}
                ),
                "url": (
                    f"https://x.com/{username}/status/{tweet.get('id')}"
                    if username
                    else f"https://x.com/i/web/status/{tweet.get('id')}"
                ),
            }
        )

    return json_result({"query": query, "count": len(posts), "posts": posts})
