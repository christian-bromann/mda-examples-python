from managed_deepagents import define_deep_agent

from tools.whoami import whoami

# Account Concierge — member-facing agent behind trusted-backend identity.
#
# Lives behind your product API: the BFF authenticates the session, stamps
# `X-MDA-Ingress-Secret` + `X-MDA-User-Id` (see `proxy/server.py`), and the
# concierge greets the member by account. `whoami` echoes the resolved identity.
# System prompt from `instructions.md`.
agent = define_deep_agent(
    name="account-concierge",
    model="openai:gpt-5.5",
    tools=[whoami],
)
