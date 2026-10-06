.PHONY: setup dev test check schema
setup:
	python3 scripts/setup_env.py
	uv sync --python 3.12 --extra ml --extra dev
	cd apps/web && npm ci
dev:
	LANGAI_GIT_COMMIT=$$(git rev-parse HEAD) docker compose up --build -d
test:
	uv run --extra ml --extra dev pytest -q
check:
	uv run --extra dev ruff check apps ml cli tests scripts
	cd apps/web && npm run typecheck && npm run build
schema:
	uv run python scripts/export_schema.py
