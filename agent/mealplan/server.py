r"""HTTP service around the meal-plan workflow (Flask, separate process).

    POST /plan   {"request": {budget, people, dietary_preferences, pantry}, "planner": "deterministic"|"llm"}
    POST /chat   {"message": "...", "pending": {...}|null, "planner": ...}
    GET  /health

No planning logic lives here: /plan calls workflow.run, /chat calls chat.interpret
and then workflow.run once the request is complete. API keys stay in this process
(read from agent\.env by the course adapter) and never appear in responses.

Run one request at a time: generate.py keeps module-level counters, so a lock
serialises runs (same reasoning as the course's serve.py).
"""

import os
import threading

from flask import Flask, jsonify, request

from . import chat, settings
from .serialize import jsonable
from .sources import ApiSource, FixtureSource
from .workflow import run

PLANNERS = ("deterministic", "llm")
_lock = threading.Lock()


def _default_model_fn():
    from generate import generate  # lazy: needs google-genai and GEMINI_API_KEY

    return lambda prompt: generate(prompt, temperature=0.0)


def _default_source():
    if os.getenv("MEALPLAN_DATA", "api") == "fixture":
        from .cli import DEFAULT_FIXTURE

        return FixtureSource(DEFAULT_FIXTURE)
    return ApiSource(settings.API_BASE_URL)


def create_app(model_fn_factory=_default_model_fn, source_factory=_default_source) -> Flask:
    app = Flask(__name__)

    def _planner_fn(planner):
        """None for deterministic; a model function for llm. Raises on model setup failure."""
        return model_fn_factory() if planner == "llm" else None

    def _run(req, planner):
        try:
            model_fn = _planner_fn(planner)
        except Exception as exc:  # e.g. google-genai not installed
            model_fn = lambda prompt: (_ for _ in ()).throw(exc)  # noqa: E731 - surfaces as model_unavailable
        return run(req, source_factory(), model_fn=model_fn)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/plan")
    def plan():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("request"), dict):
            return jsonify({"error": "Send JSON like {\"request\": {...}, \"planner\": \"deterministic\"}"}), 400
        planner = body.get("planner", "deterministic")
        if planner not in PLANNERS:
            return jsonify({"error": f"planner must be one of {list(PLANNERS)}"}), 400
        with _lock:
            result = _run(body["request"], planner)
        return jsonify({"kind": "result", "result": jsonable(result)})

    @app.post("/chat")
    def chat_turn():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("message"), str):
            return jsonify({"error": "Send JSON like {\"message\": \"...\", \"pending\": null}"}), 400
        planner = body.get("planner", "deterministic")
        if planner not in PLANNERS:
            return jsonify({"error": f"planner must be one of {list(PLANNERS)}"}), 400
        with _lock:
            try:
                extract_fn = model_fn_factory()
            except Exception as exc:
                return jsonify({"kind": "error", "error": "model_unavailable",
                                "message": f"The language model is unavailable ({exc}). Use the form below instead.",
                                "pending": chat.sanitize_pending(body.get("pending"))})
            turn = chat.interpret(body["message"], body.get("pending"), extract_fn)
            if turn["kind"] != "ready":
                return jsonify(jsonable(turn))
            result = _run(turn["request"], planner)
        return jsonify(jsonable({"kind": "result", "notes": turn["notes"], "pending": turn["pending"],
                                 "request": turn["request"], "result": result}))

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("MEALPLAN_PORT", "5001"))
    print(f"Meal-plan service on http://127.0.0.1:{port} (data: {os.getenv('MEALPLAN_DATA', 'api')})")
    app.run(host="127.0.0.1", port=port, debug=False)
