# Managed Deep Agents examples (Python)

A collection of [Managed Deep Agents](https://docs.langchain.com/langsmith/managed-deep-agents-overview)
projects that show how common MDA capabilities fit together in Python.

Each subdirectory is a deployable agent project (`mda dev` / `mda deploy`).

## Examples

| Example                                         | What it shows                                                                                                         |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| [`daily-update/`](./daily-update)               | Weekday cron digest of GitHub + Slack activity, custom tools (no connectors), Slack DM delivery, durable memory       |
| [`marketing-assistant/`](./marketing-assistant) | Weekday HN (+ optional X) topic scan → tweet drafts on Slack; revise in chat, post manually                           |
| [`policy-desk/`](./policy-desk)                 | **Policy Desk** — employees sign in, upload handbooks/policies, get cited guidance in a per-thread sandbox            |
| [`account-concierge/`](./account-concierge)     | **Account Concierge** — member agent behind your product API (session → proxy stamps ingress + user id)               |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 24+ (for `policy-desk` UI)
- A LangSmith account with Managed Deep Agents access
- The `mda` CLI (`pip install --pre managed-deepagents` or via each example’s
  `uv sync`)

## Getting started

```bash
cd daily-update
uv sync
cp env.example .env
# fill secrets, then:
uv run mda dev .
```

See each example’s README for secrets, Slack/GitHub setup, and deploy steps.

## Lint

Each example uses [ruff](https://docs.astral.sh/ruff/) (format + lint) and
[ty](https://docs.astral.sh/ty/) (types):

```bash
cd daily-update
uv sync
uv run ruff format .
uv run ruff check .
uv run ty check .
```

## Deploy via GitHub Actions

Use **Actions → Deploy agent → Run workflow** and pick an agent. The workflow
runs `mda deploy` against LangSmith. When you pick `policy-desk`, it also
builds and deploys the Vite UI to Cloudflare.

Configure these repository secrets first (Settings → Secrets and variables →
Actions). Use `MDA_GITHUB_TOKEN` for your personal GitHub PAT — Actions already
owns the name `GITHUB_TOKEN`.

| Secret                       | Required                                      |
| ---------------------------- | --------------------------------------------- |
| `LANGSMITH_API_KEY`          | yes                                           |
| `OPENAI_API_KEY`             | yes                                           |
| `MDA_INGRESS_SECRET`         | account-concierge (+ channel-backed agents)   |
| `SLACK_BOT_TOKEN`            | for Slack channels                            |
| `SLACK_SIGNING_SECRET`       | for Slack channels                            |
| `SLACK_USER_TOKEN`           | for Slack search tools (`daily-update`)       |
| `MDA_GITHUB_TOKEN`           | for GitHub tools (`daily-update`)             |
| `X_BEARER_TOKEN`             | optional X search (`marketing-assistant`)     |
| `MDA_GUEST_SIGNING_KEY`      | identity runtime (`policy-desk`)              |
| `LANGSMITH_WORKSPACE_ID`     | if your key is org-scoped                     |
| `VITE_SUPABASE_URL`          | `policy-desk` identity + UI                   |
| `VITE_SUPABASE_ANON_KEY`     | `policy-desk` UI                              |
| `VITE_LANGGRAPH_API_URL`     | `policy-desk` UI (MDA deployment URL)         |
| `CLOUDFLARE_API_TOKEN`       | `policy-desk` UI                              |
| `CLOUDFLARE_ACCOUNT_ID`      | `policy-desk` UI                              |
| `MDA_SDK_TOKEN`              | if managed-deepagents-sdk is private          |
