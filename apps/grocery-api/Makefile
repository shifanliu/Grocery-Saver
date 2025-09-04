# Tools
UV := uv
PY := $(UV) run python
PIP := $(UV) run python -m pip
UVICORN := $(UV) run uvicorn

# Project settings
APP := app.main:app
PORT := 8000
HOST := 0.0.0.0

# Default target
.DEFAULT_GOAL := help

# --------------------------
# Development commands
# --------------------------

.PHONY: uv
uv:
	@echo "Installing uv CLI tool..."
	python -m pip install --upgrade pip uv
	
.PHONY: run
run: 
	@echo "Starting Uvicorn with auto-reload: $(APP) on $(HOST):$(PORT)"
	@$(UVICORN) $(APP) --host $(HOST) --port $(PORT) --reload

.PHONY: shell
shell:
	@echo "Starting Python shell inside uv environment"
	@$(PY)

.PHONY: sync
sync:
	@echo "Installing project dependencies from pyproject.toml"
	@$(UV) sync --extra dev 


.PHONY: test
test:
	@echo "Running tests with pytest and checking coverage >= 80%"
	@$(UV) run pytest --cov=app --cov-fail-under=80 tests


.PHONY: lint
lint:
	@echo "Auto-fixing code..."
	@$(UV) run isort app
	@$(UV) run black app
	@$(UV) run autoflake --in-place --remove-unused-variables --remove-all-unused-imports -r app
	@echo "Lint report (flake8 + pylint):"
	@$(UV) run flake8 app
	@$(UV) run pylint app

