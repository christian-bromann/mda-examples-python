from managed_deepagents import define_deep_agent

from middleware.stage_chat_uploads import stage_chat_uploads_middleware

# Policy Desk — employee policy / handbook assistant.
#
# Signed-in staff upload handbooks and policy PDFs; the agent stages them into
# a per-thread LangSmith sandbox, extracts text, and answers with cited guidance.
#
# Identity: `identity.py` (`auth.supabase`).
# Sandbox: `sandbox/__init__.py`. Memory: `memory.py`.
# System prompt: `instructions.md`. UI: `src/` (Vite + Supabase login).
agent = define_deep_agent(
    name="mda-example-policy-desk-py",
    model="openai:gpt-5.5",
    middleware=[stage_chat_uploads_middleware()],
)
