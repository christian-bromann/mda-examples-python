import os
from urllib.parse import urlparse

from managed_deepagents import auth, define_identity


def _supabase_project_ref() -> str:
    """Resolve the Supabase project subdomain for JWKS verification from
    ``VITE_SUPABASE_URL`` (``https://<ref>.supabase.co``).
    """
    url = (os.environ.get("VITE_SUPABASE_URL") or "").strip()
    if url:
        host = urlparse(url).hostname or ""
        ref = host.split(".")[0].strip()
        if ref:
            return ref

    msg = (
        "Set VITE_SUPABASE_URL so identity.py can resolve "
        "auth.supabase(project_ref=...)."
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
