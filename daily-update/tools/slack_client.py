"""Slack Web API helpers using the deployment user token."""

from __future__ import annotations

import json
import os
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def slack_user_token() -> str | None:
    """User token (`xoxp-…`) for search/history — not `SLACK_BOT_TOKEN`."""
    token = (
        os.environ.get("SLACK_USER_TOKEN") or os.environ.get("SLACK_MCP_TOKEN") or ""
    ).strip()
    return token or None


def slack_client_from_env() -> WebClient | dict[str, str]:
    token = slack_user_token()
    if not token:
        return {
            "error": (
                "No Slack user token configured. Set SLACK_USER_TOKEN "
                "in the deployment environment."
            )
        }
    return WebClient(token=token)


def json_result(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def slack_error(exc: SlackApiError) -> str:
    err = ""
    if isinstance(exc.response, dict):
        err = str(exc.response.get("error") or "")
    return json_result({"error": err or str(exc)})
