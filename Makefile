# Development helpers
.PHONY: dev-setup lint fmt test precommit

# One-time local setup to enable git pre-commit hooks
# Requires: pip in active virtualenv

dev-setup:
	pip install pre-commit
	pre-commit install

lint:
	ruff check .

fmt:
	ruff format .

precommit:
	pre-commit run --all-files

# Default test target; adjust env as needed
# PSN_INTEGRATION=1 will enable integration tests (requires GCP auth)

test:
	pytest -v
