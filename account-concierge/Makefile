.PHONY: agent proxy dev deploy

# Force direct OpenAI. A shell OPENAI_BASE_URL pointing at LangSmith Gateway
# (common in Cursor/LangSmith tooling) will 403 when paired with OPENAI_API_KEY.
AGENT_ENV = OPENAI_BASE_URL=https://api.openai.com/v1

agent:
	$(AGENT_ENV) uv run mda dev .

proxy:
	uv run python proxy/server.py

# Agent + proxy together. Ctrl+C stops both.
dev:
	@trap 'kill 0' EXIT INT TERM; \
		$(AGENT_ENV) uv run mda dev . & \
		uv run python proxy/server.py & \
		wait

deploy:
	uv run mda deploy .
