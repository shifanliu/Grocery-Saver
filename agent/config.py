"""
Settings for FitFindr.

Everything you're likely to change lives here, at the top, on purpose.

Two of these come up in the brief by name. If your fit cards come out
word-for-word identical every time, it is one of the two things below —
either the cache handed back an answer it already had, or TEMPERATURE is 0.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


# ─── Windows console encoding ────────────────────────────────────────────────
# You should not need to touch this.
#
# On Windows the console defaults to cp1252, which cannot represent emoji. The
# model puts emoji in fit cards all the time — it is writing captions, after
# all — so printing one would crash the program with a UnicodeEncodeError,
# after the model call had already been paid for. Every entry point imports
# config, so fixing it here fixes it everywhere.

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ─── The two settings the brief tells you about ──────────────────────────────

# How much the model varies between runs. 0.0 gives you the same words every
# time; higher gives you more variation. Fit cards want variation — a caption
# that reads identically for two different items isn't a caption, it's a
# template.
TEMPERATURE = 0.9

# While you're building, identical prompts reuse the answer already received,
# so re-running the same query twenty times while debugging costs one call.
# Evaluation runs turn this off automatically — five tries have to be five
# real answers. `run_eval.py` handles that for you.
CACHE_ENABLED = os.getenv("AI201_CACHE", "1") != "0"


# ─── The agent loop ──────────────────────────────────────────────────────────

# The most common architectural failure in production agents is a missing stop
# condition — the loop runs forever, burning quota with nothing to show for it.
# Your loop this unit is short enough that you may never hit this. Keep it
# anyway; it's the habit that matters.
MAX_ITERATIONS = 10

# How many search results to consider. The agent uses the first one.
SEARCH_RESULT_LIMIT = 10


# ─── Model ───────────────────────────────────────────────────────────────────

MODEL = os.getenv("AI201_MODEL", "gemini-3.5-flash-lite")


# ─── Rate limiting and quota guards ──────────────────────────────────────────
# You should not need to touch these.
#
# This is the heaviest pair in the course for call volume — one agent run is
# several requests, because two of your three tools call the model. Iterating
# quickly will cross the per-minute limit. The adapter paces you and says when
# it's waiting; that pause is not a bug.
#
# REQUESTS_PER_MINUTE is 15 because that is the actual free-tier limit for
# gemini-3.5-flash-lite — the API reports it as
# GenerateRequestsPerMinutePerProjectPerModel-FreeTier, quotaValue 15. Raising
# it does not buy you more quota; it just means you hit the limit at the
# service instead of being paced here, and a paced wait is much cheaper than a
# failed run. Two model calls per agent run means about seven runs a minute.

REQUESTS_PER_MINUTE = 15
SESSION_REQUEST_BUDGET = 300
MAX_RETRIES = 5

CACHE_DIR = ROOT / ".cache"


# ─── Paths ───────────────────────────────────────────────────────────────────

DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
