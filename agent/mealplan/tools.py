"""The three tools: search_products, plan_meal, compute_cost.

Tools never raise for expected conditions. They return dicts with an explicit
"status" so the loop can branch on them. All money is Decimal.
"""

import json
import math
from decimal import Decimal, InvalidOperation

from . import catalog, units
from .sources import ServiceError

# ── tool 1: search_products ──────────────────────────────────────────────────


def _normalize(raw) -> dict:
    """Validate one API row. Raises ValueError on a bad shape."""
    if not isinstance(raw, dict):
        raise ValueError("item is not an object")
    pid, name = raw.get("id"), raw.get("name")
    if pid in (None, "") or not isinstance(name, str):
        raise ValueError("item missing id or name")
    price = raw.get("price")
    parsed = None
    if price is not None and not isinstance(price, bool):
        try:
            parsed = Decimal(str(price))
        except InvalidOperation:
            raise ValueError(f"item {pid} has non-numeric price {price!r}") from None
        if not parsed.is_finite() or parsed <= 0:
            parsed = None  # zero/negative/NaN price is treated as missing
    return {
        "product_id": str(pid),
        "name": name,
        "price": parsed,  # Decimal or None (= missing)
        "store_id": raw.get("store_id"),
        "last_seen_time": raw.get("last_seen_time"),
        "category": raw.get("category"),
        "active": raw.get("active", True),
    }


def search_products(query: str, source) -> dict:
    """Search one data source.

    Returns {"status": "ok", "products": [...]} (products may be EMPTY: that is
    a real "nothing found") or {"status": "service_unavailable", "message": ...}
    (the source failed: NOT the same as nothing found).
    """
    try:
        raw_items = source.search(query)
        products = [_normalize(r) for r in raw_items]
    except ServiceError as exc:
        return {"status": "service_unavailable", "message": str(exc), "products": []}
    except ValueError as exc:
        return {"status": "service_unavailable",
                "message": f"unexpected response shape: {exc}", "products": []}
    products = [p for p in products if p["active"] is not False]
    return {"status": "ok", "products": products}


# ── tool 3: compute_cost ─────────────────────────────────────────────────────


def _unsupported(message: str, **extra) -> dict:
    return {"status": "unsupported_data", "message": message, **extra}


def compute_cost(template_ids: list[str], selection: dict, people: int,
                 pantry: list[dict], packages: dict | None = None) -> dict:
    """Whole-package cost of the ingredients for the given meals.

    selection: ingredient -> normalized product record (from search results).
    pantry:    validated list of {"ingredient", "quantity": Decimal, "unit"}.
    Returns {"status": "ok", "total": Decimal, "line_items": [...], ...} or
    {"status": "unsupported_data", "message": ...}.
    Total = sum(packages_needed x package price): the cost of buying whole
    packages, excluding tax and fees. NOT the prorated cost of what is eaten.
    """
    packages = catalog.PACKAGES if packages is None else packages

    # 1. aggregate requirements per ingredient (before any rounding)
    need: dict[str, tuple[str, Decimal]] = {}  # ingredient -> (dimension, base qty)
    for tid in template_ids:
        for ing, qty, unit in catalog.TEMPLATES_BY_ID[tid].per_person:
            dim, base = units.to_base(qty * people, unit)
            prev = need.get(ing)
            if prev and prev[0] != dim:
                return _unsupported(f"template units for '{ing}' mix dimensions")
            need[ing] = (dim, base + (prev[1] if prev else Decimal(0)))

    # 2. pantry deduction (compatible units only)
    pantry_notes: list[str] = []
    have: dict[str, Decimal] = {}
    for entry in pantry:
        ing = entry["ingredient"]
        if ing not in need:
            continue
        try:
            dim, base = units.to_base(entry["quantity"], entry["unit"])
        except KeyError:
            pantry_notes.append(f"pantry {ing}: unknown unit '{entry['unit']}', not deducted")
            continue
        if dim != need[ing][0]:
            pantry_notes.append(
                f"pantry {ing}: unit '{entry['unit']}' ({dim}) is not compatible with "
                f"the recipe's {need[ing][0]} unit, not deducted")
            continue
        have[ing] = have.get(ing, Decimal(0)) + base

    # 3. whole packages
    line_items, total = [], Decimal("0")
    for ing, (dim, required) in need.items():
        product = selection.get(ing)
        if product is None:
            return _unsupported(f"no product selected for '{ing}'", ingredient=ing)
        if product["price"] is None:
            return _unsupported(
                f"product {product['product_id']} ({product['name']}) has no usable "
                f"price", ingredient=ing, product_id=product["product_id"])
        pkg = packages.get(product["product_id"])
        if pkg is None or pkg.ingredient != ing:
            return _unsupported(
                f"no verified package size for product {product['product_id']} "
                f"({product['name']})", ingredient=ing, product_id=product["product_id"])
        try:
            pkg_dim, pkg_base = units.to_base(pkg.quantity, pkg.unit)
        except KeyError:
            return _unsupported(f"unknown package unit '{pkg.unit}'", ingredient=ing)
        if pkg_dim != dim:
            return _unsupported(
                f"package unit '{pkg.unit}' ({pkg_dim}) is incompatible with the "
                f"required {dim} for '{ing}'", ingredient=ing,
                product_id=product["product_id"])
        deducted = min(have.get(ing, Decimal(0)), required)
        remaining = required - deducted
        n_packages = int(math.ceil(remaining / pkg_base)) if remaining > 0 else 0
        line_total = product["price"] * n_packages
        total += line_total
        line_items.append({
            "ingredient": ing,
            "product_id": product["product_id"],
            "product_name": product["name"],
            "unit_price": product["price"],
            "price_timestamp": product["last_seen_time"],
            "store_id": product["store_id"],
            "required": required,
            "pantry_deducted": deducted,
            "remaining": remaining,
            "base_unit": units.BASE_UNIT[dim],
            "package_size": f"{pkg.quantity} {pkg.unit}",
            "package_base_quantity": pkg_base,
            "packages_needed": n_packages,
            "line_total": line_total,
        })
    return {"status": "ok", "total": total, "line_items": line_items,
            "pantry_notes": pantry_notes,
            "basis": "whole packages, excluding tax and fees"}


# ── tool 2: plan_meal ────────────────────────────────────────────────────────


def candidates_by_ingredient(products: list[dict], ingredient: str) -> list[dict]:
    """Search-result products usable for an ingredient: mapped to a verified
    package for that ingredient AND priced. Order = catalog preference order."""
    order = list(catalog.PACKAGES)
    usable = [p for p in products
              if p["price"] is not None
              and catalog.PACKAGES.get(p["product_id"]) is not None
              and catalog.PACKAGES[p["product_id"]].ingredient == ingredient]
    return sorted(usable, key=lambda p: order.index(p["product_id"]))


def signature(plan: dict) -> tuple:
    return (plan["template_id"],
            tuple(sorted((i, p["product_id"]) for i, p in plan["selection"].items())))


def _build(template, pools, mode):
    selection = {}
    for ing in template.ingredients:
        pool = pools.get(ing) or []
        if not pool:
            return None
        selection[ing] = (min(pool, key=lambda p: (p["price"], p["product_id"]))
                          if mode == "cheapest" else pool[0])
    return {"template_id": template.id, "template_name": template.name,
            "selection": selection, "mode": mode}


def plan_meal(request: dict, pools: dict, attempted: set, adjustment: int,
              model_fn=None) -> dict:
    """Pick a meal template and one search-result product per ingredient.

    pools: ingredient -> usable products (see candidates_by_ingredient).
    Returns {"status": "ok", "plan": {...}, "planner_mode": ...},
    {"status": "no_candidate"} (nothing new to try), or
    {"status": "model_unavailable", "message": ...}.

    Deterministic planner: initial plan = first eligible template with the
    preferred product per ingredient. Adjustments = the cheapest-priced
    unattempted candidate (cheapest product per ingredient), ranked among the
    curated templates only; not a global optimum.
    LLM planner (model_fn given): the model may only name a known template ID
    and product IDs taken from `pools`; anything else is rejected.
    """
    eligible = [t for t in catalog.eligible_templates(request["dietary_preferences"])
                if all(pools.get(i) for i in t.ingredients)]
    if model_fn is not None:
        return _plan_with_model(request, eligible, pools, attempted, model_fn)

    if adjustment == 0:
        modes = ["default"]
    else:
        modes = ["cheapest"]
    cands = []
    for t in eligible:
        for mode in modes:
            plan = _build(t, pools, mode)
            if plan is None or signature(plan) in attempted:
                continue
            cost = compute_cost([t.id], plan["selection"], request["people"],
                                request["pantry"])
            rank = cost["total"] if cost["status"] == "ok" else Decimal("Infinity")
            cands.append((rank, eligible.index(t), plan))
    if not cands:
        return {"status": "no_candidate", "planner_mode": "deterministic"}
    if adjustment == 0:
        cands.sort(key=lambda c: c[1])  # catalog order
    else:
        cands.sort(key=lambda c: (c[0], c[1]))  # cheapest first
    return {"status": "ok", "plan": cands[0][2], "planner_mode": "deterministic"}


def _plan_with_model(request, eligible, pools, attempted, model_fn) -> dict:
    # The model sees ids, names and prices (all from search results) so "prefer
    # lower cost" is something it can actually act on. It still only picks ids.
    allowed = {t.id: {i: [{"id": p["product_id"], "name": p["name"], "price": str(p["price"])}
                          for p in pools[i]] for i in t.ingredients}
               for t in eligible}
    prompt = (
        "Choose ONE meal for a shopping plan. Reply with JSON only, shaped like "
        '{"template_id": "...", "product_ids": {"<ingredient>": "<product id>"}}.\n'
        "Use only these template IDs and, per ingredient, only these product IDs. "
        f"Prefer lower total cost.\nAllowed: {json.dumps(allowed)}\n"
        f"People: {request['people']}. Budget USD: {request['budget']}.\n"
        f"Already tried (do not repeat): {json.dumps(sorted(map(list, attempted)), default=str)}"
    )
    try:
        text = model_fn(prompt)
    except Exception as exc:  # any provider failure (key, network, quota)
        return {"status": "model_unavailable", "planner_mode": "llm",
                "message": f"model call failed: {exc}"}
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        choice = json.loads(text[start:end])
        tid, ids = choice["template_id"], choice["product_ids"]
        if tid not in allowed or not isinstance(ids, dict):
            raise ValueError(f"template_id {tid!r} is not an allowed template")
        selection = {}
        for ing in catalog.TEMPLATES_BY_ID[tid].ingredients:
            pid = str(ids.get(ing))
            match = [p for p in pools[ing] if p["product_id"] == pid]
            if not match:
                raise ValueError(f"product {pid!r} is not an allowed choice for '{ing}'")
            selection[ing] = match[0]
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "model_unavailable", "planner_mode": "llm",
                "message": f"model output rejected: {exc}"}
    plan = {"template_id": tid, "template_name": catalog.TEMPLATES_BY_ID[tid].name,
            "selection": selection, "mode": "llm"}
    if signature(plan) in attempted:
        return {"status": "no_candidate", "planner_mode": "llm"}
    return {"status": "ok", "plan": plan, "planner_mode": "llm"}
