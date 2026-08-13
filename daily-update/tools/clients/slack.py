"""Slack Web API helpers using the deployment user token."""

from __future__ import annotations

import json
import os
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_MISSING_USER_TOKEN = (
    "No Slack user token configured. Set SLACK_USER_TOKEN (xoxp-…) in the "
    "deployment environment. See docs/slack-user-token.md. Do not use "
    "SLACK_BOT_TOKEN here."
)
_WRONG_TOKEN_TYPE = (
    "Slack search.messages rejected the token type. It needs a user token "
    "(xoxp-…) with search:read, not SLACK_BOT_TOKEN (xoxb-…). Set "
    "SLACK_USER_TOKEN on the deployment from docs/slack-user-token.md and redeploy."
)


def slack_user_token() -> str | None:
    """User token (`xoxp-…`) for search/history — not `SLACK_BOT_TOKEN`.

    Do not fall back to connector/MCP Slack tokens — those are almost always
    bot tokens, and ``search.messages`` rejects them with
    ``not_allowed_token_type``.
    """
    token = (os.environ.get("SLACK_USER_TOKEN") or "").strip()
    return token or None


def slack_client_from_env() -> WebClient | dict[str, str]:
    token = slack_user_token()
    if not token:
        return {"error": _MISSING_USER_TOKEN}
    if not token.startswith("xoxp-"):
        kind = "a bot token (xoxb-…)" if token.startswith("xoxb-") else "a non-user token"
        return {
            "error": (
                f"SLACK_USER_TOKEN is {kind}. search.messages requires a user token "
                "(xoxp-…) with search:read. See docs/slack-user-token.md. "
                "Do not reuse SLACK_BOT_TOKEN."
            )
        }
    return WebClient(token=token)


def json_result(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def slack_error(exc: SlackApiError) -> str:
    err = _slack_api_error_code(exc)
    if err == "not_allowed_token_type":
        return json_result({"error": _WRONG_TOKEN_TYPE})
    return json_result({"error": err or str(exc)})


def _slack_api_error_code(exc: SlackApiError) -> str:
    response = exc.response
    if isinstance(response, dict):
        return str(response.get("error") or "")
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return str(data.get("error") or "")
    return ""
