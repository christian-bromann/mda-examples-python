from managed_deepagents import channels

# Slack Events — revise drafts in DMs (e.g. "make #2 sharper").
#
# Events URL after deploy:
#   `https://<deployment>/channels/slack/events`
#
# Secrets: `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN` (Events path is Slack-signed
# only). `MDA_INGRESS_SECRET` is for trusted-backend loopback into the graph,
# not Slack webhook auth.
#
# Also subscribe to the matching bot events on your Slack app:
# `message.im`, `app_mention`.
channel = channels.slack(
    auto_reply=True,
    mention_behavior="strip",
)
