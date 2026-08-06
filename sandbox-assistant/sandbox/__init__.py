"""Per-conversation LangSmith sandbox. MDA names, reuses, and tears down the environment."""

from managed_deepagents import sandboxes

sandbox = sandboxes.langsmith(
    scope="thread",
    idle_ttl_seconds=600,
    default_timeout=600,
)
