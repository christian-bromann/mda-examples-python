"""Return the member identity MDA resolved from trusted-backend ingress."""

from __future__ import annotations

import json
from collections.abc import Mapping

from langchain.tools import ToolRuntime, tool


def _plain(value: object) -> object:
    """Unwrap frozen identity mappings for JSON (runtime.identity is read-only)."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@tool
def whoami(runtime: ToolRuntime) -> str:
    """Return the signed-in member's identity (user id stamped by the product API).

    Use when they ask who they are, which account is active, or to verify the
    session reached the concierge.
    """
    # Annotate as ToolRuntime so LangGraph can inject/validate it; MDA's
    # managed-runtime wrapper overlays the frozen ``identity`` envelope.
    identity = getattr(runtime, "identity", None)
    if not identity:
        return json.dumps({"error": "No authenticated member on this run."}, indent=2)

    return json.dumps(
        {
            "user": _plain(identity["user"]),
            "groups": list(identity.get("groups") or ()),
            "source": _plain(identity["source"]),
            "claims": _plain(identity.get("claims") or {}),
        },
        indent=2,
    )
