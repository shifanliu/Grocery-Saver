"""Command line: structured JSON in, result + trace out.

    python -m mealplan --request demo/success.json
    python -m mealplan --request demo/success.json --data fixture
    python -m mealplan --request demo/success.json --planner llm   (live model call!)
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from . import settings
from .sources import ApiSource, FixtureSource, ServiceError
from .workflow import run

DEFAULT_FIXTURE = Path(__file__).resolve().parent.parent / "data" / "mealplan_fixture.json"


def _model_fn():
    """Live model through the course adapter (generate.py). Only used with --planner llm."""
    from generate import generate  # lazy: needs google-genai + GEMINI_API_KEY

    return lambda prompt: generate(prompt, temperature=0.0)


def render(result: dict) -> str:
    out = [f"STATUS: {result['status']}", result["message"], ""]
    data = result["data"]
    out.append(f"data source : {data['mode']} - {data['label']}")
    out.append(f"price dates : {', '.join(data['price_dates']) or 'n/a'}")
    for w in data["warnings"]:
        out.append(f"WARNING     : {w}")
    out.append(f"planner mode: {result['planner_mode']}")
    cost = result.get("cost")
    if cost:
        out += ["", f"{'ingredient':<10} {'product':<8} {'need':>9} {'pantry':>8} {'pkgs':>4} "
                    f"{'price':>7} {'line':>8}  package"]
        for li in cost["line_items"]:
            out.append(f"{li['ingredient']:<10} {li['product_id']:<8} "
                       f"{li['required']:>8.0f}{li['base_unit'][:1]} {li['pantry_deducted']:>7.0f}{li['base_unit'][:1]} "
                       f"{li['packages_needed']:>4} {li['unit_price']:>7} {li['line_total']:>8}  "
                       f"{li['package_size']} ({li['product_name'][:40]})")
        out.append(f"TOTAL ${cost['total']}  ({cost['basis']})")
        out += [f"note: {n}" for n in cost["pantry_notes"]]
    out += ["", "TRACE:"] + [f"  {n}. {line}" for n, line in enumerate(result["trace"], 1)]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mealplan")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--request", help="path to a JSON request file")
    src.add_argument("--request-json", help="inline JSON request")
    ap.add_argument("--data", choices=["api", "fixture"], default="api")
    ap.add_argument("--api-url", default=settings.API_BASE_URL)
    ap.add_argument("--store-id", help="restrict API search to one store id")
    ap.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    ap.add_argument("--planner", choices=["deterministic", "llm"], default="deterministic")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)

    try:
        text = Path(args.request).read_text(encoding="utf-8") if args.request else args.request_json
        request = json.loads(text)
    except (OSError, ValueError) as exc:
        print(f"Cannot read request: {exc}", file=sys.stderr)
        return 2

    try:
        source = (ApiSource(args.api_url, store_id=args.store_id) if args.data == "api"
                  else FixtureSource(args.fixture))
    except ServiceError as exc:
        print(f"Cannot open data source: {exc}", file=sys.stderr)
        return 2

    model_fn = None
    if args.planner == "llm":
        try:
            model_fn = _model_fn()
        except Exception as exc:  # missing package etc.
            print(f"LLM planner unavailable: {exc}", file=sys.stderr)
            return 2

    result = run(request, source, model_fn=model_fn)
    if args.json:
        print(json.dumps(result, indent=2, default=lambda o: str(o) if isinstance(o, Decimal) else list(o)))
    else:
        print(render(result))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
