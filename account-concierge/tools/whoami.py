"""Return the member identity MDA resolved from trusted-backend ingress."""

from __future__ import annotations

import json

from langchain.tools import tool
from managed_deepagents import ManagedDeepAgentRuntime


@tool
def whoami(runtime: ManagedDeepAgentRuntime) -> str:
    """Return the signed-in member's identity (user id stamped by the product API).

    Use when they ask who they are, which account is active, or to verify the
    session reached the concierge.
    """
    identity = runtime.identity
    if not identity:
        return json.dumps({"error": "No authenticated member on this run."}, indent=2)

    return json.dumps(
        {
            "user": identity["user"],
            "groups": list(identity.get("groups") or ()),
            "source": identity["source"],
            "claims": identity.get("claims") or {},
        },
        indent=2,
    )
