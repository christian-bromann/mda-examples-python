"""Resolve the authenticated Linear account for the deployment API key."""

from __future__ import annotations

from langchain.tools import tool

from tools.clients.linear import json_result, linear_graphql


@tool
def get_linear_user() -> str:
    """Return the Linear user for the deployment LINEAR_API_KEY.

    Call this before gathering Linear activity.
    """
    result = linear_graphql(
        """
        query GetLinearViewer {
          viewer {
            id
            name
            displayName
            email
          }
        }
        """
    )
    if "error" in result:
        return json_result(result)

    viewer = result["data"]["viewer"]
    return json_result(
        {
            "id": viewer["id"],
            "name": viewer["name"],
            "displayName": viewer["displayName"],
            "email": viewer["email"],
        }
    )
