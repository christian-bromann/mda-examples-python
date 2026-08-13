"""Deployment-scoped Linear GraphQL helpers (stdlib urllib — no SDK)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, TypedDict


class LinearGraphqlError(TypedDict):
    error: str


class LinearGraphqlSuccess(TypedDict):
    data: dict[str, Any]


LINEAR_API_URL = "https://api.linear.app/graphql"


def linear_api_key() -> str | None:
    key = (os.environ.get("LINEAR_API_KEY") or "").strip()
    return key or None


def json_result(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def linear_graphql(
    query: str,
    variables: dict[str, Any] | None = None,
) -> LinearGraphqlSuccess | LinearGraphqlError:
    """Run a Linear GraphQL query with the deployment API key."""
    api_key = linear_api_key()
    if not api_key:
        return {
            "error": (
                "No Linear API key configured. Set LINEAR_API_KEY in the deployment environment."
            )
        }

    payload: dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    request = urllib.request.Request(
        LINEAR_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"error": (f"Linear GraphQL HTTP {exc.code}. Check LINEAR_API_KEY scopes.")}
        errors = body.get("errors") or []
        first = errors[0].get("message") if errors else None
        return {"error": first or f"Linear GraphQL HTTP {exc.code}. Check LINEAR_API_KEY scopes."}
    except urllib.error.URLError as exc:
        return {"error": f"Linear request failed: {exc.reason}"}
    except json.JSONDecodeError:
        return {"error": "Linear returned non-JSON."}

    errors = body.get("errors") or []
    if errors:
        return {"error": "; ".join(str(err.get("message") or "Unknown error") for err in errors)}

    data = body.get("data")
    if data is None:
        return {"error": "Linear GraphQL returned no data."}

    return {"data": data}
