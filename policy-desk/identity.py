import os
from urllib.parse import urlparse

from managed_deepagents import auth, define_identity


def _supabase_project_ref() -> str:
    """Resolve the Supabase project subdomain for JWKS verification.

    Prefer ``SUPABASE_PROJECT_REF``, otherwise parse
    ``SUPABASE_URL`` / ``VITE_SUPABASE_URL`` (``https://<ref>.supabase.co``).
    """
    explicit = (os.environ.get("SUPABASE_PROJECT_REF") or "").strip()
    if explicit:
        return explicit

    url = (os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL") or "").strip()
    if url:
        host = urlparse(url).hostname or ""
        ref = host.split(".")[0].strip()
        if ref:
            return ref

    msg = (
        "Set SUPABASE_PROJECT_REF or SUPABASE_URL (or VITE_SUPABASE_URL) so "
        "identity.py can resolve auth.supabase(project_ref=...)."
    )
    raise ValueError(msg)


# Browser-direct Supabase auth for the Policy Desk UI.
#
# MDA verifies JWTs via JWKS — the browser sends
# ``Authorization: Bearer <access_token>`` on every agent call.
#
# Default identity scope gives each signed-in employee private threads (and
# thus private per-thread sandboxes for their policy uploads).
identity = define_identity(
    auth=auth.supabase(project_ref=_supabase_project_ref()),
)
