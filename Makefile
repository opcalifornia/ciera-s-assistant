.PHONY: dev test eval seed lint typecheck fmt down logs

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

# Runs the backend test suite against an in-memory Mongo (mongomock) —
# no Docker services required, no cost.
test:
	cd api && pip install -q -e ".[dev]" && pytest

# Validates the eval fixture set (Section 13). No LLM calls, no cost.
eval:
	cd api && pip install -q -e ".[dev]" && python -m evals.runner

# Seeds a demo workspace/user/brand into the local docker-compose Mongo.
# Run `make dev` in another terminal first.
seed:
	MONGODB_URI=mongodb://localhost:27017 python3 seed/demo_workspace.py

lint:
	cd api && ruff check .
	cd web && npm run lint

typecheck:
	cd api && mypy app
	cd web && npm run typecheck

fmt:
	cd api && ruff format .
