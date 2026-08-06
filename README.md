# Managed Deep Agents examples (Python)

A collection of [Managed Deep Agents](https://docs.langchain.com/langsmith/managed-deep-agents-overview)
projects that show how common MDA capabilities fit together in Python.

Each subdirectory is a deployable agent project (`mda dev` / `mda deploy`).

## Examples

| Example                                         | What it shows                                                                                                         |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| [`daily-update/`](./daily-update)               | Weekday cron digest of GitHub + Slack activity, custom tools (no connectors), Slack DM delivery, durable memory       |
| [`marketing-assistant/`](./marketing-assistant) | Weekday HN (+ optional X) topic scan → tweet drafts on Slack; revise in chat, post manually                           |
| [`sandbox-assistant/`](./sandbox-assistant)     | Supabase login → browser chat; per-thread LangSmith sandbox assistant; UI on Cloudflare Workers                       |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 24+ (for `sandbox-assistant` UI)
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
runs `mda deploy` against LangSmith. When you pick `sandbox-assistant`, it also
builds and deploys the Vite UI to Cloudflare.

Configure these repository secrets first (Settings → Secrets and variables →
Actions). Use `MDA_GITHUB_TOKEN` for your personal GitHub PAT — Actions already
owns the name `GITHUB_TOKEN`.

| Secret                       | Required                                      |
| ---------------------------- | --------------------------------------------- |
| `LANGSMITH_API_KEY`          | yes                                           |
| `OPENAI_API_KEY`             | yes                                           |
| `MDA_INGRESS_SECRET`         | trusted-backend                               |
| `SLACK_BOT_TOKEN`            | for Slack channels                            |
| `SLACK_SIGNING_SECRET`       | for Slack channels                            |
| `SLACK_USER_TOKEN`           | for Slack search tools (`daily-update`)       |
| `MDA_GITHUB_TOKEN`           | for GitHub tools (`daily-update`)             |
| `X_BEARER_TOKEN`             | optional X search (`marketing-assistant`)     |
| `MDA_GUEST_SIGNING_KEY`      | identity runtime (`sandbox-assistant`)        |
| `LANGSMITH_WORKSPACE_ID`     | if your key is org-scoped                     |
| `VITE_SUPABASE_URL`          | `sandbox-assistant` identity + UI             |
| `VITE_SUPABASE_ANON_KEY`     | `sandbox-assistant` UI                        |
| `VITE_LANGGRAPH_API_URL`     | `sandbox-assistant` UI (MDA deployment URL)   |
| `CLOUDFLARE_API_TOKEN`       | `sandbox-assistant` UI                        |
| `CLOUDFLARE_ACCOUNT_ID`      | `sandbox-assistant` UI                        |
| `MDA_SDK_TOKEN`              | if managed-deepagents-sdk is private          |
