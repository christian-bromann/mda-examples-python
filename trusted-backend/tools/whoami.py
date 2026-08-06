"""Return the caller identity MDA resolved from trusted-backend ingress."""

from __future__ import annotations

import json

from langchain.tools import tool
from managed_deepagents import ManagedDeepAgentRuntime


@tool
def whoami(runtime: ManagedDeepAgentRuntime) -> str:
    """Return the authenticated caller's identity (user id from the trusted backend).

    Use when the user asks who they are or to verify auth is working.
    """
    identity = runtime.identity
    if not identity:
        return json.dumps({"error": "No authenticated caller on this run."}, indent=2)

    return json.dumps(
        {
            "user": identity["user"],
            "groups": list(identity.get("groups") or ()),
            "source": identity["source"],
            "claims": identity.get("claims") or {},
        },
        indent=2,
    )
