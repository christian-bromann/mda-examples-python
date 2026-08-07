from managed_deepagents import define_deep_agent

from tools.get_github_user import get_github_user
from tools.get_slack_thread import get_slack_thread
from tools.list_github_events import list_github_events
from tools.search_github_commits import search_github_commits
from tools.search_github_issues import search_github_issues
from tools.search_github_pull_requests import search_github_pull_requests
from tools.search_slack_messages import search_slack_messages

# Daily update agent — GitHub + Slack activity digest via authored tools,
# Slack DM delivery from `schedules/morning_digest.py`, and durable notes under
# `/memories/agent/daily/`. System prompt from `instructions.md`.
#
# GitHub and Slack access use deployment secrets (`GITHUB_TOKEN`,
# `SLACK_USER_TOKEN`) from `.env` — not connectors.
agent = define_deep_agent(
    name="mda-example-daily-update-py",
    model="openai:gpt-5.5",
    tools=[
        get_github_user,
        list_github_events,
        search_github_pull_requests,
        search_github_issues,
        search_github_commits,
        search_slack_messages,
        get_slack_thread,
    ],
)
