from managed_deepagents import define_deep_agent

from tools.get_x_user_timeline import get_x_user_timeline
from tools.search_hackernews import search_hackernews
from tools.search_x_posts import search_x_posts

# Marketing assistant — scan public discussion (HN always; X optional),
# draft tweets from `/memories/agent/focus.md`, DM on Slack for manual posting.
#
# Durable memory requires root `memory.py` (`define_memory(scope="agent")`).
# Secrets from `.env` (see `env.example`) — not connectors.
# System prompt from `instructions.md`.
agent = define_deep_agent(
    name="mda-example-marketing-assistant-py",
    model="openai:gpt-5.5",
    tools=[search_hackernews, search_x_posts, get_x_user_timeline],
)
