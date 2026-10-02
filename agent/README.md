# Grocery Meal Planner (rule-based tool workflow with optional LLM planning)

Given a budget, number of people, dietary preference and pantry, it searches
Grocery Saver products, picks a curated meal, and computes the cost of the
**whole packages you would have to buy** (excluding tax and fees; not the
prorated cost of what is eaten). Code lives in `mealplan/`. `generate.py` and `config.py` (Gemini adapter and settings) come from a
course starter template; the rest of that template is not included here.

What it is: a fixed `search -> plan -> compute cost` workflow whose branching is
plain `if` statements on tool results, with at most 2 adjustment attempts.
What it is not: a model-driven agent, multi-turn memory (state is per request),
or a price optimiser. An LLM can optionally pick the meal inside `plan_meal`
(`--planner llm`), constrained to known template and product IDs.

## Setup (Windows PowerShell)

```powershell
# 1. Agent project (Python 3.11-3.13). The deterministic CLI and the tests need only the stdlib + pytest.
cd Grocery-Saver\agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest tests -q          # 39 tests, mocked HTTP and model, no network

# 2. Grocery Saver API, only needed for --data api. Leave this window open.
cd Grocery-Saver\apps\grocery_api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`uv run` uses the project environment at the repo-root `.venv` (pyproject.toml and uv.lock live at the
repo root and already include `openai` and `jinja2`). No `uv sync` is needed if that
environment exists; do not use `apps\grocery_api\.venv`, a stale, unused venv. Startup takes
10-15 seconds. It serves the committed SQLite file `data\grocery.db` (`REPO_TYPE` defaults to
`db`). `GROCERY_API_URL` (default `http://127.0.0.1:8000`) or `--api-url` points the agent elsewhere.
Check it: `Invoke-RestMethod "http://127.0.0.1:8000/items/search?q=rice"`.

## Run

```powershell
cd Grocery-Saver\agent
.\.venv\Scripts\python.exe -m mealplan --request demo\success.json                 # API data
.\.venv\Scripts\python.exe -m mealplan --request demo\success.json --data fixture  # offline snapshot, no server
.\.venv\Scripts\python.exe -m mealplan --request demo\success.json --json          # machine-readable
```

Demos (all deterministic, no model call; numbers are identical with `--data fixture`):

| Demo | Command (after `cd Grocery-Saver\agent`) | Expected |
|---|---|---|
| success | `.\.venv\Scripts\python.exe -m mealplan --request demo\success.json` | `success`, bean and rice bowl, $37.17 |
| budget adjustment | `... --request demo\adjust.json` | initial $45.96 is over $40, adjustment 1 switches to bean tacos, `success`, $23.76 |
| over budget | `... --request demo\over_budget.json` | 3 candidates tried, cheapest $23.76 vs $15, `over_budget` |
| empty result | `... --request demo\success.json --store-id NO_SUCH_STORE` | `no_results` (offline: `--data fixture --fixture demo\empty_fixture.json`) |
| API down | `... --request demo\success.json --api-url http://127.0.0.1:9` | `service_unavailable` (not `no_results`) |

## Input

```json
{"budget": 60, "people": 2, "dietary_preferences": ["vegan"],
 "pantry": [{"ingredient": "onion", "quantity": 500, "unit": "g"}]}
```

- `budget`: positive USD. `people`: positive integer.
- `dietary_preferences`: only `vegetarian`, `vegan`, `high_protein` (tags hand-assigned to the 12 curated meals); `high_protein` is also supported (see Fitness meals).
- `pantry`: ingredient (rice, beans, tomatoes, onion, potatoes, eggs, tofu, broccoli, carrots,
  pasta, tortillas, chicken, oats), quantity, unit (`g kg oz lb ml l count dozen`). Deducted only
  when the unit dimension matches (mass vs mass, count vs count); otherwise noted and ignored.

Statuses: `success`, `over_budget`, `no_results`, `unsupported_data`, `service_unavailable`,
`model_unavailable`, `invalid_request`. The result also carries the original request unchanged,
`data.mode` (`api`/`fixture`) and label, `planner_mode`, line items, attempts and a trace.

## Known limitations

- One meal per plan. Twelve curated templates (6 general + 6 fitness). Quantities per person are rough planning numbers.
- Package sizes are a hand-made map for 24 product IDs (`mealplan/catalog.py`), read off product
  names; the API has no size field. Anything else is `unsupported_data`, by design.
- The data is Costco Business Delivery bulk packs only (50 lb rice, 10 lb onions), so whole-package
  totals are far above a "meal" price. Items sold by weight whose listed price looks per-lb
  (e.g. chicken breast "9 lb avg wt" at $2.99) are deliberately not mapped, because the price basis is unverified.
- Prices come from the `price` field (`promotion_price` is ignored). The committed DB is dated 2026-07-22; the result warns when data is older than 14 days.
- Adjustment only ranks the curated candidates it generated; it never claims the cheapest basket overall.
- Dietary tags come from my reading of each meal's ingredients. They are **not allergen detection
  or medical advice**; products' own ingredient lists were not checked.
- No Flask/HTTP endpoint for the planner, no frontend, no MCP.
- Fixture `data/mealplan_fixture.json` is a **real-data snapshot** (rows copied read-only from the
  Grocery Saver DB, dated 2026-07-22), not synthetic. Test fixtures built inline in tests are labelled synthetic.

## Verification status

Verified by execution: the 39 tests pass; mutation checks (floor instead of ceil; disabling the
repeat-candidate guard) make tests fail. CLI runs against the live local Grocery Saver API
(`success`, `adjust`, `over_budget`, `no_results` via `--store-id`, `service_unavailable` via a dead port)
and against the fixture, each from a fresh PowerShell with no extra environment variables. `--planner llm` with no
API key was run: it ended `model_unavailable` before any network call. Live LLM: one run of demo\success.json with --planner llm returned success (1 model call, bean_tacos, $14.97, IDs all from search results); only that single case was tried. Not verified beyond it: retries/adjustments with a live model, malformed live output
(the LLM path is otherwise tested with mocks only), Safeway data (none in the DB), and the Postgres/docker-compose setup.

## Three-minute walkthrough

1. (30s) Problem and framing: budget + people + diet + pantry -> shopping plan. It is a rule-based
   tool workflow with optional LLM planning, not a free-roaming agent.
2. (45s) Run `demo/success.json`: show the three tools in the trace, then the line items: price and
   timestamp come from the Grocery Saver API, package sizes from a separate reviewed map, and
   `packages_needed = ceil(remaining / package_size)` in Decimal.
3. (45s) Run `demo/adjust.json`: initial plan is $45.96 over $40, the loop picks a different candidate,
   recomputes, stops at $23.76. Point out the bound (2 adjustments), the attempted-candidate set, and the
   `over_budget` demo that ends honestly instead of claiming a global optimum.
4. (30s) Failure handling: empty results vs API down vs model failure are different statuses; no silent
   fallback to fixture data or to another planner; data source and planner mode are always printed.
5. (30s) Honest limits: curated catalog, bulk Costco data, 70-day-old prices, per-lb items excluded, dietary
   tags are not allergen detection.


## LLM planner (optional; one live smoke test passed 2026-10-01)

`--planner llm` calls the course adapter `generate.py`: Google Gemini through `google-genai`, model
`gemini-3.5-flash-lite` (override with `AI201_MODEL`), temperature 0, key `GEMINI_API_KEY` read from
`agent\.env` (copy `.env.example`; git-ignored). Extra installs: `python-dotenv`, `google-genai`.
The adapter paces to 15 requests/minute, retries rate limits (possibly waiting up to a minute), caches
identical prompts in `.cache\`, and stops at 300 calls per session.

The model decides only which curated meal template and which search-result product per ingredient.
It sees allowed template IDs plus product ids/names/prices from the search. Code validates the answer
(JSON parses, template allowed, each product id is among the searched, priced, size-mapped products for
that ingredient; a repeat is treated as "nothing new"). Costing, budget comparison, retry bound and
status are all code. A call failure or rejected output ends as `model_unavailable`; there is no silent
fallback to the deterministic planner. At most 3 model calls per run.

Smoke test (1-3 live calls; needs your authorization and a key in `agent\.env`):
`.\.venv\Scripts\python.exe -m mealplan --request demo\success.json --planner llm`

## Interactive UI (Meal Planner panel in Grocery Saver)

The existing Grocery Saver page (Jinja + vanilla JS, no framework) has a "Meal Planner" panel with
its own chat history, example prompts, a rule-based / Gemini planner switch, and a structured form
fallback ("Use the form instead"). Browser -> Grocery Saver `POST /planner/chat` or `/planner/plan`
(same origin, validated by pydantic) -> agent service `POST /chat` or `/plan` (Flask, port 5001) ->
`mealplan.workflow.run`. The two Python environments stay separate; the Gemini key is read only by
the agent process from `agent\.env` and never reaches the browser or Grocery Saver.

Start (two PowerShell windows, leave both open):

```powershell
# window 1: Grocery Saver (API + UI) on http://127.0.0.1:8000
cd Grocery-Saver\apps\grocery_api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# window 2: meal-plan agent service on http://127.0.0.1:5001
cd Grocery-Saver\agent
.\.venv\Scripts\python.exe -m pip install "flask>=3.0,<4.0" "python-dotenv>=1.0,<1.2" "google-genai>=1.0,<2.0"   # first time only
.\.venv\Scripts\python.exe -m mealplan.server
```

Then open http://127.0.0.1:8000/. Config: `PLANNER_SERVICE_URL` (default `http://127.0.0.1:5001`) and
`PLANNER_TIMEOUT_SECONDS` (default 60) for Grocery Saver; `GROCERY_API_URL`, `MEALPLAN_PORT`,
`MEALPLAN_DATA=fixture` (offline snapshot) for the agent service.

Interview inputs (type into the chat):

1. Success: `Plan a vegetarian dinner for 2 under $40. I have 500 g of onions.` -> Bean and rice bowl, $37.17.
2. Budget adjustment: `Vegan dinner for 2 under $30` -> initial bean rice bowl $45.96 is over, adjustment 1
   picks Bean tacos at $23.76. (Form equivalent: budget 30, people 2, vegan.)
3. Clarification: `Vegan dinner for 3 people` -> asks for the budget; reply `$50`.

How chat works: Gemini only reads the message into fields (one call per message); code validates every
value, never guesses a missing budget, people count or pantry amount (it asks), keeps the collected
fields client-side as `pending` (conversation state, re-validated each turn), and starts the workflow
only when complete. A failed extraction is shown as an error; the form still works. Choosing "Gemini
picks the meal" adds the planner calls described above.

Product links: the data has no retailer URL (the collectors do not store one), so links go to the
internal "View product details" page `/products/<store>:<id>`, added only for products that exist in the
DB. "View at retailer" would appear only for a verified http(s) URL; none exist today.

Changed files:

| Repo | File | Role |
|---|---|---|
| agent | `mealplan/server.py` | Flask `/plan`, `/chat`, `/health` around the workflow |
| agent | `mealplan/chat.py` | message -> validated request, clarification, pending state |
| agent | `mealplan/serialize.py` | Decimal-safe JSON |
| agent | `tests/test_chat_server.py` | 20+ tests with a mocked model |
| grocery | `app/routers/planner.py` | same-origin proxy, validation, product links, error mapping |
| grocery | `app/main.py` | registers router; `/products/{id}` page |
| grocery | `app/templates/index.html`, `product.html` | panel markup; detail page |
| grocery | `app/static/planner.js`, `style.css` | panel logic (textContent only) and styles |
| grocery | `tests/test_planner_router.py` | proxy, validation, links, failures, escaping |

Verification: agent tests (71) and Grocery Saver tests (38 passed, 1 skipped) pass with mocked HTTP and model.
Executed for real: both services running together; form and chat requests through the real page; links
resolve (HTTP 200 to the selected products); agent-service-down error shown in the panel; submit button
disabled while busy; no horizontal overflow at 375 px width. Live Gemini: exactly 3 calls total for the UI
smoke test (success prompt, incomplete prompt, answer to the clarification), all deterministic planner.
Not verified: the Gemini planner from the UI, visual appearance (the browser pane could not take
screenshots), slow-model timeouts in the browser.

Limitations: one meal per request; chat state is in the page, so a reload clears it; development
servers only; the two services must both be started by hand; ingredients outside the 12 catalog items
are ignored with a note; model extraction can misread a message, so the plan always echoes the structured
request it used.

## Fitness meals (`high_protein`)

Six extra templates in `mealplan/catalog.py` (`_FIT`), tagged `high_protein`, combinable with
`vegetarian`/`vegan`: chicken_broccoli_power_bowl (about 42 g protein/serving), chicken_bean_chili (37),
egg_veggie_scramble (31, vegetarian), savory_egg_oats (34, vegetarian), tofu_rice_power_bowl (39, vegan),
tofu_bean_scramble (35, vegan). A new `oats` ingredient maps two verified products (446586 Quaker 10 lb,
731962 Bob's Red Mill 112 oz). "High protein" means the template's estimated protein is at least 30 g per
serving, from a small hand-entered per-ingredient table in the same file (typical published values,
as-purchased/dry weights, no cooking losses or brand differences). The estimate is shown in the plan as
"approx." and is not nutrition advice; there are no calorie or macro targets. A test checks every tag against the estimate.

Demos: `demo\high_protein.json` (1 person, $25: chicken bowl $48.47 is over, adjustment picks savory oats
with eggs at $15.48) and `demo\vegan_high_protein.json` (ends `over_budget`: cheapest $33.35 vs $30).
Chat examples: `High-protein meal for 1 under $25`, `Vegan high-protein dinner for 2, budget $50`.