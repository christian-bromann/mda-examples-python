.PHONY: agent proxy dev deploy

agent:
	uv run mda dev .

proxy:
	uv run python proxy/server.py

# Agent + proxy together. Ctrl+C stops both.
dev:
	@trap 'kill 0' EXIT INT TERM; \
		uv run mda dev . & \
		uv run python proxy/server.py & \
		wait

deploy:
	uv run mda deploy .
