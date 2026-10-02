"""The rule-based loop: search -> plan -> compute cost, with bounded adjustment.

Which step runs next is decided by plain `if` statements on tool results, not
by a model. An LLM may optionally be used inside plan_meal only.

State lives in a request-scoped `session` dict created per run(); nothing is
kept between runs (this is NOT multi-turn memory).

Statuses: success, over_budget, no_results, unsupported_data,
service_unavailable, model_unavailable, invalid_request.
"""

import copy
from datetime import date
from decimal import Decimal, InvalidOperation

from . import catalog, settings, units
from .tools import candidates_by_ingredient, compute_cost, plan_meal, search_products, signature


# ── request validation ───────────────────────────────────────────────────────


def _decimal(value, what, errors, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        errors.append(f"{what} must be a number")
        return None
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        errors.append(f"{what} must be a number")
        return None
    if not d.is_finite() or d < 0 or (d == 0 and not allow_zero):
        errors.append(f"{what} must be {'non-negative' if allow_zero else 'positive'}")
        return None
    return d


def validate_request(raw) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["request must be a JSON object"]
    budget = _decimal(raw.get("budget"), "budget (USD)", errors)
    people = raw.get("people")
    if isinstance(people, bool) or not isinstance(people, int) or people <= 0:
        errors.append("people must be a positive integer")
    prefs = raw.get("dietary_preferences", [])
    if not isinstance(prefs, list) or any(not isinstance(p, str) for p in prefs):
        errors.append("dietary_preferences must be a list of strings")
        prefs = []
    prefs = [p.strip().lower() for p in prefs]
    bad = [p for p in prefs if p not in settings.SUPPORTED_PREFERENCES]
    if bad:
        errors.append(f"unsupported dietary preference(s) {bad}; supported: "
                      f"{list(settings.SUPPORTED_PREFERENCES)}")
    pantry_raw = raw.get("pantry", [])
    pantry = []
    if not isinstance(pantry_raw, list):
        errors.append("pantry must be a list of {ingredient, quantity, unit}")
        pantry_raw = []
    for n, entry in enumerate(pantry_raw):
        if not isinstance(entry, dict) or not isinstance(entry.get("ingredient"), str):
            errors.append(f"pantry[{n}] needs ingredient/quantity/unit")
            continue
        qty = _decimal(entry.get("quantity"), f"pantry[{n}].quantity", errors, allow_zero=True)
        unit = entry.get("unit")
        if unit not in units.UNITS:
            errors.append(f"pantry[{n}].unit must be one of {sorted(units.UNITS)}")
        elif qty is not None:
            pantry.append({"ingredient": entry["ingredient"].strip().lower(),
                           "quantity": qty, "unit": unit})
    if errors:
        return None, errors
    return {"budget": budget, "people": people,
            "dietary_preferences": prefs, "pantry": pantry}, []


# ── helpers ──────────────────────────────────────────────────────────────────


def _data_info(source, products, today):
    stamps = sorted({str(p["last_seen_time"])[:10] for p in products if p.get("last_seen_time")})
    info = {"mode": source.mode, "label": source.label,
            "price_dates": stamps, "warnings": []}
    if stamps:
        try:
            age = (today - date.fromisoformat(stamps[-1])).days
            if age > settings.STALE_AFTER_DAYS:
                info["warnings"].append(
                    f"newest price in use is {age} days old (dated {stamps[-1]}); "
                    "prices may have changed")
        except ValueError:
            pass
    return info


def _plan_view(plan, request):
    template = catalog.TEMPLATES_BY_ID[plan["template_id"]]
    return {"template_id": template.id, "name": template.name, "people": request["people"],
            "tags": sorted(template.tags),
            "est_protein_g_per_serving": template.est_protein_g}  # rough estimate, see catalog


def _attempt_view(n, plan, cost):
    view = {"attempt": n, "template_id": plan["template_id"], "planner_mode": plan["mode"],
            "products": {i: p["product_id"] for i, p in plan["selection"].items()},
            "status": cost["status"]}
    if cost["status"] == "ok":
        view["total"] = cost["total"]
    else:
        view["reason"] = cost["message"]
    return view


# ── the loop ─────────────────────────────────────────────────────────────────


def run(raw_request, source, model_fn=None, today: date | None = None) -> dict:
    """Run the workflow once. Never raises for expected failures."""
    today = today or date.today()
    session = {
        "original_request": copy.deepcopy(raw_request),  # returned unchanged
        "request": None,
        "products": [],
        "pools": {},
        "attempted": set(),
        "attempts": [],
        "trace": [],
    }
    planner_mode = "llm" if model_fn else "deterministic"
    trace = session["trace"]

    def finish(status, message, plan=None, cost=None):
        return {
            "status": status,
            "message": message,
            "request": session["original_request"],
            "planner_mode": planner_mode,
            "data": _data_info(source, session["products"], today),
            "plan": plan,
            "cost": cost,
            "attempts": session["attempts"],
            "trace": trace,
        }

    request, errors = validate_request(raw_request)
    if errors:
        trace.append("validate_request: rejected -> " + "; ".join(errors))
        return finish("invalid_request", "Invalid request: " + "; ".join(errors))
    session["request"] = request
    trace.append(f"validate_request: ok (budget ${request['budget']}, people {request['people']}, "
                 f"preferences {request['dietary_preferences'] or 'none'}, "
                 f"{len(request['pantry'])} pantry entries); data={source.mode}, planner={planner_mode}")

    # step 1: search every ingredient any eligible meal needs
    eligible = catalog.eligible_templates(request["dietary_preferences"])
    if not eligible:
        return finish("unsupported_data", "No curated meal template satisfies these preferences.")
    wanted = sorted({i for t in eligible for i in t.ingredients})
    returned_counts: dict[str, int] = {}
    for ing in wanted:
        result = search_products(catalog.SEARCH_TERMS[ing], source)
        if result["status"] == "service_unavailable":
            trace.append(f"search_products('{catalog.SEARCH_TERMS[ing]}'): SERVICE ERROR -> stopping")
            return finish("service_unavailable",
                          f"Product data is unavailable ({result['message']}). "
                          "This is a service failure, not an empty search result.")
        products = result["products"]
        session["products"].extend(products)
        returned_counts[ing] = len(products)
        session["pools"][ing] = candidates_by_ingredient(products, ing)
        trace.append(f"search_products('{catalog.SEARCH_TERMS[ing]}'): {len(products)} returned, "
                     f"{len(session['pools'][ing])} usable (verified package size + price)")

    # branch: can any eligible meal be built from usable products?
    pools = session["pools"]
    feasible = [t for t in eligible if all(pools[i] for i in t.ingredients)]
    if not feasible:
        blocked = sorted({i for t in eligible for i in t.ingredients if not pools[i]})
        empty = [i for i in blocked if returned_counts[i] == 0]
        other = [i for i in blocked if returned_counts[i] > 0]
        detail = []
        if empty:
            detail.append("no search results for: " + ", ".join(empty))
        if other:
            detail.append("results returned but none with a verified package size and a price "
                          "for: " + ", ".join(other))
        trace.append("branch: no eligible meal is buildable -> stopping (" + "; ".join(detail) + ")")
        status = "no_results" if not other else "unsupported_data"
        return finish(status, "Cannot build a plan: " + "; ".join(detail) + ".")
    trace.append(f"branch: {len(feasible)} of {len(eligible)} eligible meals are buildable")

    # step 2/3: plan -> cost, adjusting at most MAX_ADJUSTMENTS times
    best = None  # (total, plan, cost)
    for n in range(1 + settings.MAX_ADJUSTMENTS):
        label = "initial plan" if n == 0 else f"adjustment {n}/{settings.MAX_ADJUSTMENTS}"
        planned = plan_meal(request, pools, session["attempted"], n, model_fn)
        if planned["status"] == "model_unavailable":
            trace.append(f"plan_meal ({label}): MODEL FAILURE -> {planned['message']}")
            return finish("model_unavailable", planned["message"] +
                          " Re-run with the deterministic planner to continue without a model.")
        if planned["status"] == "no_candidate":
            trace.append(f"plan_meal ({label}): no new candidate to try -> stopping")
            break
        plan = planned["plan"]
        session["attempted"].add(signature(plan))
        trace.append(f"plan_meal ({label}, {planned['planner_mode']}): {plan['template_id']} "
                     f"[{plan['mode']} products: "
                     + ", ".join(f"{i}={p['product_id']}" for i, p in plan["selection"].items()) + "]")
        cost = compute_cost([plan["template_id"]], plan["selection"], request["people"],
                            request["pantry"])
        session["attempts"].append(_attempt_view(n, plan, cost))
        if cost["status"] != "ok":
            trace.append(f"compute_cost: UNSUPPORTED -> {cost['message']}")
            continue
        trace.append(f"compute_cost: ${cost['total']} vs budget ${request['budget']}")
        if best is None or cost["total"] < best[0]:
            best = (cost["total"], plan, cost)
        if cost["total"] <= request["budget"]:
            trace.append("terminate: within budget")
            plan_view = _plan_view(plan, request)
            return finish("success",
                          f"Plan '{plan['template_name']}' costs ${cost['total']} "
                          f"(budget ${request['budget']}): whole packages, excluding tax and fees. "
                          "This is the cost of what you must buy, not the prorated cost of what "
                          "is eaten.", plan_view, cost)
        trace.append("branch: over budget -> " + (
            "trying a different candidate" if n < settings.MAX_ADJUSTMENTS else
            "adjustment limit reached"))

    if best is None:
        trace.append("terminate: no candidate could be costed")
        return finish("unsupported_data",
                      "No candidate could be costed; see attempts for the unsupported product/unit.")
    total, plan, cost = best
    trace.append("terminate: over budget after bounded adjustment")
    plan_view = _plan_view(plan, request)
    return finish("over_budget",
                  f"Over budget: the cheapest of the {len(session['attempts'])} candidate(s) tried "
                  f"costs ${total} vs budget ${request['budget']} (short by "
                  f"${total - request['budget']}). Only a limited set of curated meals was tried; "
                  "this is not a claim that no cheaper basket exists.", plan_view, cost)
