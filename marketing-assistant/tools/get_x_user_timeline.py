"""Fetch recent original posts from an X watch-account username."""

from __future__ import annotations

from langchain.tools import tool

from tools.json_result import json_result
from tools.x_client import x_bearer_or_skip, x_error, x_get


@tool
def get_x_user_timeline(username: str, max_results: int = 25) -> str:
    """Fetch recent original posts from an X username in focus.md Watch accounts.

    For zeitgeist, use max_results ~20-30 per account.

    Args:
        username: Handle with or without @.
        max_results: Max posts to return (default 25, capped at 50).
    """
    token = x_bearer_or_skip()
    if isinstance(token, dict):
        return json_result(token)

    handle = username.lstrip("@")
    limit = min(max(max_results, 1), 50)

    try:
        user_payload = x_get(
            f"/users/by/username/{handle}",
            {},
            token,
        )
        user_id = (user_payload.get("data") or {}).get("id")
        if not user_id:
            return json_result({"error": f"X user not found: @{handle}"})

        api_max = max(5, min(limit, 100))
        timeline = x_get(
            f"/users/{user_id}/tweets",
            {
                "max_results": str(api_max),
                "exclude": "replies,retweets",
                "tweet.fields": "created_at,public_metrics,lang",
            },
            token,
        )
    except RuntimeError as exc:
        return x_error(exc)

    posts = []
    for tweet in (timeline.get("data") or [])[:limit]:
        posts.append(
            {
                "id": tweet.get("id"),
                "text": tweet.get("text"),
                "createdAt": tweet.get("created_at"),
                "lang": tweet.get("lang"),
                "metrics": tweet.get("public_metrics"),
                "author": {"username": handle},
                "url": f"https://x.com/{handle}/status/{tweet.get('id')}",
            }
        )

    return json_result({"username": handle, "count": len(posts), "posts": posts})
