from managed_deepagents import define_identity

# Trusted-backend identity (the MDA default).
#
# Your API authenticates the user (session cookie, OAuth, etc.), then proxies
# LangGraph requests with:
#   - `X-MDA-Ingress-Secret` — shared secret from `MDA_INGRESS_SECRET`
#   - `X-MDA-User-Id` — the authenticated user id your backend resolved
#
# The browser never sees the ingress secret. See `proxy/server.mjs` for a
# minimal stand-in for that backend.
identity = define_identity()
