from managed_deepagents import define_memory

# Deployment-shared durable memory at `/memories/agent/` (read/write).
#
# Hot: `/memories/agent/AGENTS.md` (Recent drafts + short pointers).
# Cold: `/memories/agent/focus.md`, `/memories/agent/drafts/YYYY-MM-DD.md`.
#
# Python MDA requires an explicit memory declaration; without this file the
# agent keeps nothing between runs.
memory = define_memory(scope="agent")
