# Acceptance criteria — Grocery Meal Agent (MVP)

The system is a rule-based tool workflow (search -> plan -> compute cost) with
an optional LLM planner. Each criterion below is checked by an automated test
in `tests/` using mocked HTTP and mocked model responses (no live API or paid
model calls).

1. **Prices and IDs come from search results.**
   For a successful run, every `product_id` in the plan's line items appears in
   the records returned by `search_products`, and each line item's unit price
   equals that record's price exactly (Decimal equality).

2. **Cost arithmetic is verified by fixed cases.**
   Fixed test inputs verify: (a) whole-package rounding
   `packages_needed = ceil(remaining / package_quantity)`; (b) required
   quantities scale with `people`; (c) pantry deduction applies only when units
   are compatible (incompatible units are not deducted); (d) requirements for
   the same ingredient are aggregated before rounding; (e) the total equals the
   `Decimal` sum of `packages_needed x package_price`.

3. **Over-budget handling is bounded and distinct.**
   When the initial plan exceeds the budget, the loop tries a different
   candidate (different meal or product), recomputes cost, never repeats an
   already-attempted candidate, and makes at most 2 adjustment attempts after
   the initial plan. If none fits, the status is `over_budget` and the result
   states the cheapest cost found among the attempted candidates (not a claim
   of a global minimum).

4. **Missing data yields explicit statuses.**
   An empty search result gives `no_results`; a product with a missing/null
   price, or a product with no verified package-size mapping or an incompatible
   unit, gives `unsupported_data` (naming the product/ingredient). In none of
   these cases are products or costs invented.

5. **Failures terminate cleanly with context.**
   A forced API failure gives `service_unavailable` (distinct from
   `no_results`); a forced LLM failure gives `model_unavailable`. Both return
   without an unhandled exception, include the original request (budget,
   people, preferences, pantry) unchanged, and report the planner mode and data
   source mode (`api` or `fixture`) in the result.
