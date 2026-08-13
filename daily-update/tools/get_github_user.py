"""Resolve the authenticated GitHub account for the deployment token."""

from __future__ import annotations

from github.GithubException import GithubException
from langchain.tools import tool

from tools.clients.github import github_error, github_from_env, json_result


@tool
def get_github_user() -> str:
    """Return the GitHub login/name for the deployment GITHUB_TOKEN.

    Call this before gathering activity.
    """
    client = github_from_env()
    if isinstance(client, dict):
        return json_result(client)

    try:
        user = client.get_user()
        return json_result(
            {
                "login": user.login,
                "name": user.name,
                "url": user.html_url,
            }
        )
    except GithubException as exc:
        return github_error(exc)
