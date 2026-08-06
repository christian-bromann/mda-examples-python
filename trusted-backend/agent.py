from managed_deepagents import define_deep_agent

from tools.whoami import whoami

# Minimal agent behind trusted-backend identity.
#
# Callers must reach the deployment through a backend that stamps
# `X-MDA-Ingress-Secret` + `X-MDA-User-Id` (see `proxy/server.mjs`).
# The only tool, `whoami`, echoes the resolved identity.
# System prompt from `instructions.md`.
agent = define_deep_agent(
    name="trusted-backend",
    model="openai:gpt-5.5",
    tools=[whoami],
)
