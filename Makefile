.PHONY: lint lint-fix format-check format check test

# Run ruff linter
lint:
	uv run --extra dev ruff check src/ tests/

# Auto-fix linter issues
lint-fix:
	uv run --extra dev ruff check --fix src/ tests/

# Check formatting (no changes)
format-check:
	uv run --extra dev ruff format --check src/ tests/

# Auto-format code
format:
	uv run --extra dev ruff format src/ tests/

# Lint + format check (CI-friendly, no modifications)
check: lint format-check

# Run tests
test:
	uv run --extra test pytest tests/ -v
