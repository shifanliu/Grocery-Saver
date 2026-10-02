"""Conversational input -> structured request.

Two kinds of state are kept apart on purpose:

* `pending` is CONVERSATION state: the fields collected so far across chat turns
  (plus the last question asked). The client holds it and sends it back each
  turn; it is re-validated here every time, never trusted.
* The workflow's per-request `session` (workflow.run) starts only once the
  request is complete, and is not shared between turns.

The model's only job here is to read the user's words into fields. Everything it
returns is validated in code; missing values are asked for, never guessed.
"""

import json
from decimal import Decimal, InvalidOperation

from . import catalog, settings, units

MAX_MESSAGE_CHARS = 500

# plural / singular forms people actually type -> catalog ingredient key
_ALIASES = {"onions": "onion", "tomato": "tomatoes", "potato": "potatoes", "bean": "beans",
            "egg": "eggs", "carrot": "carrots", "tortilla": "tortillas", "noodles": "pasta",
            "spaghetti": "pasta"}


# diet words people use -> supported preference key
_DIET_ALIASES = {"high protein": "high_protein", "high-protein": "high_protein",
                 "high_protein": "high_protein", "protein": "high_protein",
                 "fitness": "high_protein", "gym": "high_protein"}


def empty_pending() -> dict:
    return {"budget": None, "people": None, "dietary_preferences": [], "diet_stated": False,
            "diet_blocked": [], "pantry": [], "pantry_missing_qty": [], "last_question": ""}


def _num(value):
    """Positive finite Decimal from int/float/str, else None (bools rejected)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return d.normalize() if d.is_finite() and 0 < d <= 10_000_000 else None


def _fmt(d: Decimal) -> str:
    """Plain decimal text without exponent or trailing zeros (40.0 -> '40')."""
    return format(d.normalize(), "f")


def _ingredient(name):
    if not isinstance(name, str):
        return None
    n = name.strip().lower()
    n = _ALIASES.get(n, n)
    return n if n in catalog.SEARCH_TERMS else None


def sanitize_pending(raw) -> dict:
    """Rebuild a pending dict from untrusted client JSON, keeping only valid fields."""
    out = empty_pending()
    if not isinstance(raw, dict):
        return out
    b = _num(raw.get("budget"))
    out["budget"] = _fmt(b) if b is not None else None
    p = raw.get("people")
    if isinstance(p, int) and not isinstance(p, bool) and p > 0:
        out["people"] = p
    prefs = raw.get("dietary_preferences")
    if isinstance(prefs, list):
        out["dietary_preferences"] = [x for x in prefs if x in settings.SUPPORTED_PREFERENCES]
    out["diet_stated"] = raw.get("diet_stated") is True
    out["diet_blocked"] = [x[:40] for x in raw.get("diet_blocked", [])[:5] if isinstance(x, str)] \
        if isinstance(raw.get("diet_blocked"), list) else []
    if isinstance(raw.get("pantry"), list):
        for e in raw["pantry"]:
            if isinstance(e, dict) and _ingredient(e.get("ingredient")) == e.get("ingredient") \
                    and _num(e.get("quantity")) is not None and e.get("unit") in units.UNITS:
                out["pantry"].append({"ingredient": e["ingredient"],
                                      "quantity": _fmt(_num(e["quantity"])), "unit": e["unit"]})
    if isinstance(raw.get("pantry_missing_qty"), list):
        out["pantry_missing_qty"] = [i for i in raw["pantry_missing_qty"] if i in catalog.SEARCH_TERMS]
    q = raw.get("last_question")
    out["last_question"] = q[:300] if isinstance(q, str) else ""
    return out


def _prompt(message: str, pending: dict) -> str:
    return (
        "Read the shopper's message into JSON. Output JSON only, with exactly these keys:\n"
        '{"starts_new_request": bool, "budget": number|null, "people": integer|null,\n'
        ' "dietary_preferences": [string], "dietary_preferences_stated": bool,\n'
        ' "pantry": [{"ingredient": string, "quantity": number|null, "unit": string|null}]}\n'
        "Rules: use null when a value is not stated; NEVER guess or infer a number. budget is a total in "
        "US dollars. people is how many are eating. dietary_preferences uses the shopper's own words "
        "(e.g. vegetarian, vegan, high protein, gluten-free); set dietary_preferences_stated true if they said anything "
        "about diet, including 'no restrictions' (then the list is empty). pantry lists ingredients they "
        "already have at home; quantity and unit exactly as stated (g, kg, oz, lb, ml, l, count, dozen, "
        "or whatever unit they used); quantity null if no amount was given. starts_new_request is true "
        "only if the shopper clearly begins a different plan from scratch.\n"
        f"Context, already collected: {json.dumps({k: pending[k] for k in ('budget', 'people', 'dietary_preferences', 'pantry')})}\n"
        f"The assistant last asked: {json.dumps(pending['last_question'])}\n"
        f"Shopper message: {json.dumps(message)}"
    )


def _parse(text: str):
    start, end = text.index("{"), text.rindex("}") + 1
    data = json.loads(text[start:end])
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def interpret(message, pending_raw, model_fn) -> dict:
    """One conversational turn. Returns
    {"kind": "ask"|"ready"|"error", "message": str, "pending": dict, "request": dict|None, "notes": [..]}.
    A model failure is an explicit "error"; there is no regex fallback.
    """
    pending = sanitize_pending(pending_raw)
    if not isinstance(message, str) or not message.strip():
        return {"kind": "error", "error": "invalid_input", "message": "Please type a request.",
                "pending": pending, "request": None, "notes": []}
    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        return {"kind": "error", "error": "invalid_input", "pending": pending, "request": None,
                "message": f"Message is too long (max {MAX_MESSAGE_CHARS} characters).", "notes": []}
    try:
        data = _parse(model_fn(_prompt(message, pending)))
    except (ValueError, KeyError, TypeError) as exc:
        return {"kind": "error", "error": "model_unavailable", "pending": pending, "request": None,
                "message": f"I couldn't read the model's answer ({exc}). Use the form below, or rephrase.",
                "notes": []}
    except Exception as exc:  # provider failure: key, network, quota
        return {"kind": "error", "error": "model_unavailable", "pending": pending, "request": None,
                "message": f"The language model is unavailable ({exc}). Use the form below instead.",
                "notes": []}

    notes: list[str] = []
    if data.get("starts_new_request") is True:
        if any(pending[k] for k in ("budget", "people", "pantry", "diet_stated")):
            notes.append("Started a new plan.")
        pending = empty_pending()

    b = _num(data.get("budget"))
    if b is not None:
        pending["budget"] = _fmt(b)
    p = data.get("people")
    if isinstance(p, float) and p.is_integer():
        p = int(p)
    if isinstance(p, int) and not isinstance(p, bool) and p > 0:
        pending["people"] = p

    if data.get("dietary_preferences_stated") is True:
        said = data.get("dietary_preferences")
        said = [str(x).strip().lower() for x in said] if isinstance(said, list) else []
        said = [_DIET_ALIASES.get(x, x) for x in said]
        pending["dietary_preferences"] = [x for x in said if x in settings.SUPPORTED_PREFERENCES]
        pending["diet_blocked"] = [x for x in said if x not in settings.SUPPORTED_PREFERENCES][:5]
        pending["diet_stated"] = True

    entries = data.get("pantry") if isinstance(data.get("pantry"), list) else []
    bad_unit: list[str] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        ing = _ingredient(e.get("ingredient"))
        if ing is None:
            raw_name = str(e.get("ingredient"))[:40]
            notes.append(f"'{raw_name}' isn't used by any meal I can plan, so I ignored it.")
            continue
        q, unit = _num(e.get("quantity")), e.get("unit")
        unit = unit.strip().lower() if isinstance(unit, str) else unit
        if q is None:
            if ing not in pending["pantry_missing_qty"]:
                pending["pantry_missing_qty"].append(ing)
            continue
        if unit not in units.UNITS:
            bad_unit.append(ing)
            if ing not in pending["pantry_missing_qty"]:
                pending["pantry_missing_qty"].append(ing)
            continue
        pending["pantry"] = [x for x in pending["pantry"] if x["ingredient"] != ing]
        pending["pantry"].append({"ingredient": ing, "quantity": _fmt(q), "unit": unit})
        pending["pantry_missing_qty"] = [i for i in pending["pantry_missing_qty"] if i != ing]

    # what is still missing? ask one specific question
    question = None
    if pending["budget"] is None and pending["people"] is None:
        question = "What's your total budget in USD, and how many people is this for?"
    elif pending["budget"] is None:
        question = "What's your total budget in USD?"
    elif pending["people"] is None:
        question = "How many people is this for?"
    elif pending["pantry_missing_qty"]:
        ing = pending["pantry_missing_qty"][0]
        why = (f" I can use {', '.join(sorted(units.UNITS))}." if ing in bad_unit else "")
        question = f"How much {ing} do you have at home (for example 500 g)?{why}"
    elif pending["diet_blocked"]:
        question = (f"I can only plan for {' or '.join(settings.SUPPORTED_PREFERENCES)}; "
                    f"I can't handle '{', '.join(pending['diet_blocked'])}'. Tell me vegetarian, vegan, "
                    "or 'no restrictions' to continue.")
    if question:
        pending["last_question"] = question
        return {"kind": "ask", "message": question, "pending": pending, "request": None, "notes": notes}

    if not pending["diet_stated"]:
        notes.append("No dietary preference was given, so none was applied.")
    request = {"budget": pending["budget"], "people": pending["people"],
               "dietary_preferences": pending["dietary_preferences"],
               "pantry": [dict(x) for x in pending["pantry"]]}
    pending["last_question"] = ""
    return {"kind": "ready", "message": "", "pending": pending, "request": request, "notes": notes}
