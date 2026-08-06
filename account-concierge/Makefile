.PHONY: ensure-mda agent proxy dev deploy

ensure-mda:
	uv run python scripts/ensure_mda_binary.py

agent: ensure-mda
	uv run mda dev .

proxy:
	uv run python proxy/server.py

# Agent + proxy together. Ctrl+C stops both.
dev: ensure-mda
	@trap 'kill 0' EXIT INT TERM; \
		uv run mda dev . & \
		uv run python proxy/server.py & \
		wait

deploy: ensure-mda
	uv run mda deploy .
