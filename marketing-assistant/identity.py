from managed_deepagents import define_identity

# Personal marketing bot reached by Slack Events and weekday cron.
#
# Default trusted-backend ingress is enough for channel + schedule traffic.
# Durable shared memory is declared in `memory.py` (`define_memory`), not here.
#
# Do not set Slack OAuth client id/secret unless you also want
# Connect-with-Slack — without that path, DMs invoke the agent directly.
identity = define_identity(auth="backend")
