"""Per-conversation LangSmith sandbox. MDA names, reuses, and tears down the environment."""

from managed_deepagents import define_sandbox

sandbox = define_sandbox(
    scope="thread",
    idle_ttl_seconds=600,
    default_timeout=600,
)
