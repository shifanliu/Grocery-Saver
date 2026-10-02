# Grocery Saver

Grocery Saver collects grocery prices (Costco Business Delivery, plus a Safeway collector), stores them in a
database, and serves them through a FastAPI app with a web page for searching items and keeping a basket.

It also integrates a **Meal Planner** panel, backed by a separate agent service. You type something like
*"Plan a vegetarian dinner for 2 under $40. I have 500 g of onions."* and get:

- product search against Grocery Saver's own data
- natural-language input with clarification questions when something is missing
- a budget-aware plan for one meal, with at most two automatic adjustments if it is over budget
- pantry deduction (only when units are compatible)
- a whole-package purchase total (what you must buy, excluding tax and fees)
- an approximate protein estimate per serving, and a `high_protein` option

## Tech stack

| Part | Technology |
|---|---|
| Frontend | Jinja templates, vanilla JavaScript, CSS (no React, no TypeScript; `apps/dashboard` is only a placeholder README) |
| Backend | FastAPI, SQLAlchemy |
| Database | SQLite file `data/grocery.db`, committed to this repo and refreshed weekly by `.github/workflows/scrape-weekly.yml`. PostgreSQL is only an unmaintained option via `DATABASE_URL`; `infra/compose.yaml` is not used by the current setup |
| Collectors | Python scripts in `apps/grocery_collector` (requests, lxml) |
| Meal-planner agent | Separate repo, Flask service, rule-based workflow (no MCP) |
| AI | Gemini via `google-genai` for reading chat messages and, optionally, picking the meal. The older "Suggest recipes" button uses OpenAI (`OPENAI_API_KEY`) |
| Tooling | `uv` (this repo, root `pyproject.toml` and `uv.lock`) and a plain `venv` + pip (agent repo) |

## Layout

The meal planner lives in a **separate sibling repository**. It is not included when you clone Grocery Saver;
clone or copy it next to this repo (the agent code is on branch `feature/grocery-meal-agent`, not yet on its `main`).

```
GrocerySaver/
├── grocery/                      # this repo
│   ├── pyproject.toml, uv.lock   # dependencies (environment: grocery/.venv)
│   ├── data/grocery.db           # SQLite data (tracked in git)
│   ├── apps/
│   │   ├── grocery_api/          # FastAPI app: app/main.py, routers/ (items, stores, recipes, planner),
│   │   │   │                     #   templates/, static/ (app.js, planner.js, style.css), tests/
│   │   │   └── API_CONTRACTS.md  # endpoint contracts
│   │   ├── grocery_collector/    # price collectors
│   │   └── dashboard/            # placeholder only
│   └── .github/workflows/        # CI and weekly scrape
└── agent/                        # sibling repo: meal-planner agent
    ├── mealplan/                 # server.py (Flask), chat.py, workflow.py, tools.py, catalog.py
    ├── tests/, demo/, data/      # tests, demo requests, offline fixture
    └── MEALPLAN_README.md        # detailed workflow, testing, limitations
```

Request flow: **browser** → `POST /planner/chat` or `/planner/plan` on Grocery Saver (FastAPI validates the input
and acts as a same-origin proxy) → **agent service** (Flask, port 5001) → the agent queries Grocery Saver's
`GET /items/search` for products and prices, and returns a plan → the proxy adds links to product pages → browser.
The Gemini key is only ever read by the agent service.

## Setup (first time only)

Requirements: Windows PowerShell, [uv](https://docs.astral.sh/uv/), Python 3.11 to 3.13 (the agent's pinned
packages do not support 3.14). Replace the paths if your folders differ.

```powershell
# 1. Grocery Saver (creates grocery\.venv from uv.lock)
cd GrocerySaver\grocery
uv sync

# 2. Meal-planner agent (separate virtual environment)
cd ..\agent
git checkout feature/grocery-meal-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "flask>=3.0,<4.0" "python-dotenv>=1.0,<1.2" "google-genai>=1.0,<2.0"

# 3. Gemini key for chat and the optional LLM planner (the rule-based form works without it)
Copy-Item .env.example .env
notepad .env        # set GEMINI_API_KEY=... ; .env is git-ignored, never commit or paste it anywhere
```

Data: a fresh clone already contains `data/grocery.db` (1,223 Costco items, prices dated 2026-07-22 at the time of
writing). You do not need to run the collectors. The planner warns when prices are more than 14 days old.

Optional: `OPENAI_API_KEY` in `grocery\.env` (copy `.env.example`) enables the "Suggest recipes" button only.

## Run (every time, two terminals)

```powershell
# Terminal 1: Grocery Saver on http://127.0.0.1:8000
cd GrocerySaver\grocery\apps\grocery_api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: meal-planner agent service on http://127.0.0.1:5001
cd GrocerySaver\agent
.\.venv\Scripts\python.exe -m mealplan.server
```

Open **http://127.0.0.1:8000/**. Startup of Grocery Saver takes 10 to 15 seconds. API docs are at `/docs`.
Optional settings: `PLANNER_SERVICE_URL` and `PLANNER_TIMEOUT_SECONDS` (Grocery Saver), `GROCERY_API_URL`,
`MEALPLAN_PORT` and `MEALPLAN_DATA=fixture` (agent service; `fixture` uses an offline snapshot instead of the API).

## Using the Meal Planner

Type into the panel, for example:

- `Plan a vegetarian dinner for 2 under $40. I have 500 g of onions.`
- `Vegan high-protein dinner for 2, budget $50`

If budget, number of people, a pantry amount, or a supported diet is missing, it asks a specific question and keeps
what you already said until the plan is complete. **Use the form instead** (below the chat) submits the same fields
without any language model. Supported diets: vegetarian, vegan, high protein.

Gemini plays two separate roles. By default it only reads your message into fields (one call per message), and
code validates every value. If you choose **Gemini picks the meal**, it also selects the meal and products, but only
from known template IDs and the products returned by the search. Prices, package maths, totals and the budget check
are always computed in code. Product names link to **View product details**, an internal page showing the stored
data; no retailer URLs exist in the data, so none are shown.

## Tests

```powershell
cd GrocerySaver\grocery; uv sync --extra dev; cd apps\grocery_api; uv run pytest tests
cd GrocerySaver\agent; .\.venv\Scripts\python.exe -m pip install pytest; .\.venv\Scripts\python.exe -m pytest tests
```

## Limitations

- One meal per request, chosen from 12 curated templates (6 general, 6 high-protein).
- Package sizes are mapped by hand for a limited set of products; anything else is reported as unsupported.
- Prices are scraped snapshots, not live retailer pricing, and are mostly bulk Costco Business packs.
- Protein figures are rough estimates from typical food values, not personalized nutrition advice. Dietary tags are
  hand-assigned and are not allergen detection.
- Refreshing the page clears the chat state.
- Both local services must be running; they are development servers.

More detail on the workflow, statuses and testing: [agent/MEALPLAN_README.md](../agent/MEALPLAN_README.md)
(in the sibling repo).
