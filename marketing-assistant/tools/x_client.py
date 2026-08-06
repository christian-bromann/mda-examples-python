"""App-only Bearer helpers for X API v2 reads (stdlib HTTP)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from tools.json_result import json_result

X_API_BASE = "https://api.x.com/2"


def bearer_token() -> str | None:
    token = (os.environ.get("X_BEARER_TOKEN") or "").strip()
    return token or None


def x_bearer_or_skip() -> str | dict[str, Any]:
    token = bearer_token()
    if not token:
        return {
            "skipped": True,
            "error": (
                "X is optional. Set X_BEARER_TOKEN to enable search_x_posts / get_x_user_timeline."
            ),
        }
    return token


def x_get(path: str, params: dict[str, str], token: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{X_API_BASE}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "marketing-assistant/0.0.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X API error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"X API request failed: {exc.reason}") from exc


def x_error(exc: Exception) -> str:
    return json_result({"error": str(exc)})
