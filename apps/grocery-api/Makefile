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

.PHONY: run
run: 
	@echo "Starting Uvicorn with auto-reload: $(APP) on $(HOST):$(PORT)"
	@$(UVICORN) $(APP) --host $(HOST) --port $(PORT) --reload

.PHONY: shell
shell:
	@echo "Starting Python shell inside uv environment"
	@$(PY)

.PHONY: install
install:
	@echo "Installing project dependencies from pyproject.toml"
	@$(UV) sync
