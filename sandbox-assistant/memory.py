from managed_deepagents import define_memory

# Deployment-shared procedural memory at `/memories/agent/`.
# Per-conversation work lives in the thread sandbox, not here.
memory = define_memory(scope="agent")
