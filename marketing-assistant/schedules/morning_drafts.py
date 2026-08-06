from managed_deepagents import define_schedule

# Your Slack user ID (starts with `U`). Must stay a string literal in
# `deliver_to` so `mda` can statically extract it into the cron delivery target.
#
# Find it: Slack → profile → ⋯ → Copy member ID. DM the bot once after install
# so Slack opens the IM channel.
SLACK_USER_ID = "U097E05JJAF"

PROMPT = """
Run the daily marketing draft (America/Los_Angeles). Follow instructions.md
end-to-end:
1) read_file /memories/agent/focus.md — if missing, write_file the starter from
   instructions.md, then continue; also skim recent
   /memories/agent/drafts/*.md so you do not repeat yesterday's topics,
2) scan broadly for zeitgeist from focus.md niches — always try several
   search_hackernews queries (~20 hits each); if X_BEARER_TOKEN exists, several
   search_x_posts queries (~25-50 hits each) plus get_x_user_timeline for each
   watch account (~20-30). Read enough volume (~50-150 items when X is on) to
   see recurring themes; if a source is skipped/errors, continue,
3) synthesize a short zeitgeist note, then pick topics and draft exactly 3
   tweet options grounded in real sources (no invented virality),
4) write "/memories/agent/drafts/YYYY-MM-DD.md" (include Zeitgeist section)
   and refresh the Recent drafts list in /memories/agent/AGENTS.md,
5) end with a concise Slack-ready message listing the 3 drafts + short why +
   source links so I can copy-paste to X myself. deliver_to.auto_post sends the
   DM — this agent never publishes to X.
"""

schedule = define_schedule(
    # 9:00am Pacific, Monday-Friday
    cron="0 9 * * 1-5",
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
