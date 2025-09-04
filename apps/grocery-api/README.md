# Grocery API

## Using pyproject.toml with uv

This project declares dependencies in pyproject.toml and keeps requirements.txt for compatibility.

Quick setup (from repository root: apps/grocery-api):

1. Install uv (if missing)
   ```bash
   make uv
   ```

2. Create a virtual environment and install packages (via Makefile)
   ```bash
   # creates venv and installs dependencies
   make sync
   ```
   
3. Run the app 
    ```bash
    make run
    ```

4. Code reformat and linting
   ```bash
   make lint
   ```

5. Local testing
   ```bash
   make test
   ```

