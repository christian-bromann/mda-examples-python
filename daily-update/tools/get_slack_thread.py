"""Read a Slack channel or thread when a search hit needs more context."""

from __future__ import annotations

from langchain.tools import tool
from slack_sdk.errors import SlackApiError

from tools.clients.slack import json_result, slack_client_from_env, slack_error


@tool
def get_slack_thread(
    channel_id: str,
    thread_ts: str | None = None,
    limit: int = 30,
) -> str:
    """Read recent messages from a Slack channel, or a thread when thread_ts is set.

    Use after search_slack_messages when a hit needs detail.

    Args:
        channel_id: Slack channel/IM/MPIM id (C…/D…/G…).
        thread_ts: Parent message ts to read a thread; omit for channel history.
        limit: Max messages to return (default 30, max 50).
    """
    client = slack_client_from_env()
    if isinstance(client, dict):
        return json_result(client)

    capped = min(max(limit, 1), 50)
    try:
        if thread_ts:
            result = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=capped,
            )
            if not result.get("ok"):
                return json_result(
                    {"error": result.get("error") or "Slack conversations.replies failed"}
                )
            return json_result(
                [
                    {
                        "user": m.get("user"),
                        "text": m.get("text"),
                        "ts": m.get("ts"),
                    }
                    for m in (result.get("messages") or [])
                ]
            )

        result = client.conversations_history(channel=channel_id, limit=capped)
        if not result.get("ok"):
            return json_result(
                {"error": result.get("error") or "Slack conversations.history failed"}
            )
        return json_result(
            [
                {
                    "user": m.get("user"),
                    "text": m.get("text"),
                    "ts": m.get("ts"),
                    "threadTs": m.get("thread_ts"),
                }
                for m in (result.get("messages") or [])
            ]
        )
    except SlackApiError as exc:
        return slack_error(exc)
