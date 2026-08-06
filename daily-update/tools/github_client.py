"""Deployment-scoped GitHub helpers for authored tools."""

from __future__ import annotations

import json
import os
from typing import Any

from github import Auth, Github
from github.GithubException import GithubException


def github_token() -> str | None:
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT") or "").strip()
    return token or None


def github_from_env() -> Github | dict[str, str]:
    token = github_token()
    if not token:
        return {
            "error": (
                "No GitHub token configured. Set GITHUB_TOKEN (or GITHUB_PAT) "
                "in the deployment environment."
            )
        }
    return Github(auth=Auth.Token(token))


def json_result(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def github_error(exc: GithubException) -> str:
    return json_result({"error": f"GitHub API error: {exc.data or exc}"})
