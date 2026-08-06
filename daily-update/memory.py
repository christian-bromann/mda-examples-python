from managed_deepagents import define_memory

# Deployment-shared digests and workstream notes at `/memories/agent/`.
#
# Hot: `/memories/agent/AGENTS.md` (index + living workstream map).
# Cold: `/memories/agent/daily/YYYY-MM-DD.md` (one file per weekday run).
#
# Python MDA requires an explicit memory declaration; without this file the
# agent keeps nothing between runs.
memory = define_memory(scope="agent")
