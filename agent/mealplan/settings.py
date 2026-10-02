"""Settings for the meal-plan workflow (separate from the course's config.py)."""

import os

API_BASE_URL = os.getenv("GROCERY_API_URL", "http://127.0.0.1:8000")
API_TIMEOUT_SECONDS = 5.0

# Initial plan + at most this many adjustment attempts.
MAX_ADJUSTMENTS = 2

# Warn (never hide) when the newest price timestamp is older than this.
STALE_AFTER_DAYS = 14

SUPPORTED_PREFERENCES = ("vegetarian", "vegan", "high_protein")
