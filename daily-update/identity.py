from managed_deepagents import define_identity

# Personal digest bot reached by Slack Events and weekday cron.
#
# Default trusted-backend ingress is enough for channel + schedule traffic.
# Durable memory is declared separately in `memory.py` (shared agent slice so
# cron runs and Slack DMs see the same digests).
#
# Do not set Slack OAuth client id/secret unless you also want
# Connect-with-Slack — without that path, DMs invoke the agent directly.
identity = define_identity(auth="backend")
