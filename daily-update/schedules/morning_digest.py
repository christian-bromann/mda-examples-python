from managed_deepagents import define_schedule

# Your Slack user ID (starts with `U`). Must stay a string literal in
# `deliver_to` so `mda` can statically extract it into the cron delivery target.
#
# Find it: Slack → profile → ⋯ → Copy member ID. DM the bot once after install
# so Slack opens the IM channel.
SLACK_USER_ID = "U097E05JJAF"

# Keep this a static string literal (or top-level const) so `mda` can extract
# the cron prompt. Python does not yet support TS-style text-module imports.
PROMPT = """
Run the daily activity digest (America/Los_Angeles). Determine the window per
instructions.md step 1: previous 24 hours normally, but on Monday the previous
72 hours so Friday, Saturday and Sunday are all covered in one consolidated
weekend catch-up. Follow instructions.md end-to-end:
1) review memory first — read /memories/agent/AGENTS.md and the last few
   /memories/agent/daily/*.md files for continuity and recent themes (labels
   are not fixed — regroup when my contributions shift),
2) use Slack tools (search_slack_messages / get_slack_thread) for discussion
   framing over the same window — themes, decisions, blockers — not as a
   substitute for GitHub or Linear facts; do not send Slack messages yourself,
3) gather GitHub activity with the GitHub tools (get_github_user,
   list_github_events, search_github_pull_requests, search_github_issues,
   search_github_commits),
4) gather Linear activity with the Linear tools (get_linear_user,
   search_linear_issues, search_linear_comments) over the same window —
   skip Linear only if the API key is missing/unauthorized,
5) choose workstream headings that best fit the window's contributions; use
   Slack context to frame bullets; update the living map in AGENTS.md when the
   mix changes,
6) write "/memories/agent/daily/YYYY-MM-DD.md" and update the AGENTS.md index,
7) end with a concise standup-ready Slack message (that final message is
auto-posted to my DM — do not call Slack chat APIs yourself).
"""

schedule = define_schedule(
    # 7:00am Pacific, Monday-Friday (no Saturday / Sunday runs)
    cron="0 7 * * 1-5",
    timezone="America/Los_Angeles",
    prompt=PROMPT,
    deliver_to={
        "channel": "slack",
        "to": {
            "type": "provider_conversation",
            # Keep this a string literal (same value as SLACK_USER_ID above).
            "conversation_id": "U097E05JJAF",
        },
        "auto_post": True,
    },
)
