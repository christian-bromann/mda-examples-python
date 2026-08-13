"""Search Slack messages visible to the user token for digest framing."""

from __future__ import annotations

from langchain.tools import tool
from slack_sdk.errors import SlackApiError

from tools.clients.slack import json_result, slack_client_from_env, slack_error


@tool
def search_slack_messages(query: str, after: int | None = None, count: int = 20) -> str:
    """Search Slack messages the user token can see.

    Use for discussion framing (themes, decisions, blockers), not as proof of
    shipped GitHub work.

    Args:
        query: Slack search query. Can be empty when `after` bounds the window;
            otherwise keywords, from:<user>, in:<channel>, etc.
        after: Unix timestamp (seconds). Only messages after this time.
        count: Max matches to return (default 20, max 50).
    """
    client = slack_client_from_env()
    if isinstance(client, dict):
        return json_result(client)

    parts = [query.strip()]
    if after is not None:
        parts.append(f"after:{after}")
    search_query = " ".join(part for part in parts if part)

    try:
        result = client.search_messages(
            query=search_query,
            count=min(max(count, 1), 50),
            sort="timestamp",
            sort_dir="desc",
        )
    except SlackApiError as exc:
        return slack_error(exc)

    if not result.get("ok"):
        return json_result({"error": result.get("error") or "Slack search.messages failed"})

    matches = (result.get("messages") or {}).get("matches") or []
    return json_result(
        [
            {
                "channel": (m.get("channel") or {}).get("name")
                or (m.get("channel") or {}).get("id"),
                "channelId": (m.get("channel") or {}).get("id"),
                "user": m.get("user") or m.get("username"),
                "text": m.get("text"),
                "ts": m.get("ts"),
                "permalink": m.get("permalink"),
            }
            for m in matches
        ]
    )
