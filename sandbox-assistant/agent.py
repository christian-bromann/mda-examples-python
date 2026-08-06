from managed_deepagents import define_deep_agent

from middleware.stage_chat_uploads import stage_chat_uploads_middleware

# Sandbox assistant — Supabase-authenticated browser agent with a per-thread
# LangSmith sandbox for files + shell (`execute`).
#
# Identity: `identity.py` (`auth.supabase`).
# Sandbox: `sandbox/__init__.py`. Memory: `memory.py`.
# System prompt: `instructions.md`. UI: `src/` (Vite + Supabase login).
# Chat file uploads are staged by middleware; PDFs are extracted with pypdf.
agent = define_deep_agent(
    name="sandbox-assistant",
    model="openai:gpt-5.5",
    middleware=[stage_chat_uploads_middleware()],
)
