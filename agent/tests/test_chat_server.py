"""Conversation extraction + Flask service, with a mocked model and fixture data."""
import json

import pytest

from mealplan import chat
from mealplan.cli import DEFAULT_FIXTURE
from mealplan.server import create_app
from mealplan.sources import FixtureSource


def model_returning(*answers):
    """A fake model that returns the given dicts in order (and records prompts)."""
    calls = []
    queue = list(answers)

    def fn(prompt):
        calls.append(prompt)
        a = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(a, Exception):
            raise a
        return a if isinstance(a, str) else json.dumps(a)

    fn.calls = calls
    return fn


FULL = {"starts_new_request": False, "budget": 40, "people": 2,
        "dietary_preferences": ["vegetarian"], "dietary_preferences_stated": True,
        "pantry": [{"ingredient": "onions", "quantity": 500, "unit": "g"}]}


def test_full_request_is_ready_and_normalised():
    turn = chat.interpret("Plan a vegetarian dinner for 2 under $40. I have 500 g of onions.",
                          None, model_returning(FULL))
    assert turn["kind"] == "ready"
    assert turn["request"] == {"budget": "40", "people": 2, "dietary_preferences": ["vegetarian"],
                               "pantry": [{"ingredient": "onion", "quantity": "500", "unit": "g"}]}


def test_missing_budget_asks_specific_question_and_keeps_pending():
    first = chat.interpret("dinner for 3", None,
                           model_returning({"people": 3, "budget": None, "pantry": []}))
    assert first["kind"] == "ask" and "budget" in first["message"].lower()
    assert first["pending"]["people"] == 3
    # the clarification answer only carries the budget; people must survive from pending
    model = model_returning({"budget": 30, "people": None, "pantry": []})
    second = chat.interpret("$30", first["pending"], model)
    assert second["kind"] == "ready" and second["request"]["people"] == 3
    assert second["request"]["budget"] == "30"
    assert "How many" in model.calls[0] or "budget" in model.calls[0]  # context sent to the model
    assert first["message"] in model.calls[0]                          # last question is in context


def test_model_never_guesses_missing_pantry_quantity():
    turn = chat.interpret("vegan for 2 under 40, I have some rice", None, model_returning(
        {"budget": 40, "people": 2, "dietary_preferences": ["vegan"], "dietary_preferences_stated": True,
         "pantry": [{"ingredient": "rice", "quantity": None, "unit": None}]}))
    assert turn["kind"] == "ask" and "rice" in turn["message"]
    assert turn["request"] is None
    done = chat.interpret("2 lb", turn["pending"], model_returning(
        {"pantry": [{"ingredient": "rice", "quantity": 2, "unit": "lb"}]}))
    assert done["kind"] == "ready"
    assert done["request"]["pantry"] == [{"ingredient": "rice", "quantity": "2", "unit": "lb"}]


def test_unsupported_unit_and_ingredient_are_handled_in_code():
    turn = chat.interpret("x", None, model_returning(
        {"budget": 40, "people": 2, "pantry": [{"ingredient": "rice", "quantity": 2, "unit": "cups"},
                                              {"ingredient": "garlic", "quantity": 3, "unit": "count"}]}))
    assert turn["kind"] == "ask" and "rice" in turn["message"] and "kg" in turn["message"]
    assert any("garlic" in n for n in turn["notes"])


def test_unsupported_diet_blocks_until_clarified():
    turn = chat.interpret("x", None, model_returning(
        {"budget": 40, "people": 2, "dietary_preferences": ["gluten-free"], "dietary_preferences_stated": True}))
    assert turn["kind"] == "ask" and "gluten-free" in turn["message"] and turn["request"] is None
    ok = chat.interpret("no restrictions", turn["pending"], model_returning(
        {"dietary_preferences": [], "dietary_preferences_stated": True}))
    assert ok["kind"] == "ready" and ok["request"]["dietary_preferences"] == []


def test_new_request_resets_pending():
    pending = chat.interpret("x", None, model_returning(FULL))["pending"]
    turn = chat.interpret("actually, new plan: 3 people", pending, model_returning(
        {"starts_new_request": True, "people": 3, "budget": None}))
    assert turn["kind"] == "ask"
    assert turn["pending"]["people"] == 3 and turn["pending"]["budget"] is None
    assert turn["pending"]["pantry"] == []


@pytest.mark.parametrize("bad_budget", [-5, 0, "abc", True, 1e999, "1e999", [40]])
def test_invalid_budget_is_not_accepted(bad_budget):
    turn = chat.interpret("x", None, model_returning({"budget": bad_budget, "people": 2}))
    assert turn["kind"] == "ask" and turn["pending"]["budget"] is None and turn["pending"]["people"] == 2


@pytest.mark.parametrize("bad_people", [0, -1, 1.5, True, "two", None])
def test_invalid_people_is_not_accepted(bad_people):
    turn = chat.interpret("x", None, model_returning({"budget": 40, "people": bad_people}))
    assert turn["kind"] == "ask" and turn["pending"]["people"] is None and turn["pending"]["budget"] == "40"


def test_model_failure_and_garbage_are_explicit_errors_with_pending_preserved():
    pending = {"budget": 40, "people": 2}
    boom = chat.interpret("hi", pending, model_returning(RuntimeError("quota")))
    assert boom["kind"] == "error" and boom["error"] == "model_unavailable"
    assert boom["pending"]["budget"] == "40" and "quota" in boom["message"]
    junk = chat.interpret("hi", pending, model_returning("sure! rice is nice"))
    assert junk["kind"] == "error" and junk["pending"]["people"] == 2
    assert chat.interpret("  ", None, model_returning(FULL))["error"] == "invalid_input"
    assert chat.interpret("x" * 501, None, model_returning(FULL))["error"] == "invalid_input"


def test_pending_from_client_is_revalidated():
    dirty = {"budget": "1e999", "people": "2", "pantry": [{"ingredient": "rice", "quantity": "x", "unit": "g"}],
             "dietary_preferences": ["vegan", "<script>"], "evil": "x", "last_question": 5}
    clean = chat.sanitize_pending(dirty)
    assert clean["budget"] is None and clean["people"] is None and clean["pantry"] == []
    assert clean["dietary_preferences"] == ["vegan"] and "evil" not in clean


# -- Flask service ----------------------------------------------------------

def client(model_fn=None):
    app = create_app(model_fn_factory=lambda: model_fn or model_returning(FULL),
                     source_factory=lambda: FixtureSource(DEFAULT_FIXTURE))
    return app.test_client()


def test_plan_endpoint_runs_workflow_and_returns_json_safe_result():
    r = client().post("/plan", json={"request": {"budget": 60, "people": 2,
                                                 "dietary_preferences": ["vegan"], "pantry": []}})
    body = r.get_json()
    assert r.status_code == 200 and body["result"]["status"] == "success"
    assert isinstance(body["result"]["cost"]["total"], str)
    assert body["result"]["planner_mode"] == "deterministic" and body["result"]["data"]["mode"] == "fixture"


@pytest.mark.parametrize("payload", [None, {}, {"request": "x"}, {"request": {}, "planner": "magic"}])
def test_plan_endpoint_rejects_malformed_bodies(payload):
    r = client().post("/plan", json=payload) if payload is not None else \
        client().post("/plan", data="not json", content_type="application/json")
    assert r.status_code == 400


def test_plan_endpoint_invalid_request_is_a_workflow_status_not_a_crash():
    r = client().post("/plan", json={"request": {"budget": -1, "people": 2}})
    assert r.status_code == 200 and r.get_json()["result"]["status"] == "invalid_request"


def test_chat_endpoint_ready_runs_workflow_and_ask_does_not():
    c = client(model_returning(FULL))
    body = c.post("/chat", json={"message": "plan please"}).get_json()
    assert body["kind"] == "result" and body["result"]["status"] == "success"
    assert body["request"]["budget"] == "40"
    ask = client(model_returning({"people": 2})).post("/chat", json={"message": "for 2"}).get_json()
    assert ask["kind"] == "ask" and "result" not in ask


def test_chat_endpoint_model_failure_is_explicit():
    c = client(model_returning(RuntimeError("no key")))
    body = c.post("/chat", json={"message": "hi", "pending": {"people": 2}}).get_json()
    assert body["kind"] == "error" and body["error"] == "model_unavailable"
    assert body["pending"]["people"] == 2


def test_chat_endpoint_llm_planner_failure_does_not_fall_back():
    # extraction succeeds; the planner model then fails -> model_unavailable, no deterministic plan
    c = client(model_returning(FULL, RuntimeError("planner down")))
    body = c.post("/chat", json={"message": "plan", "planner": "llm"}).get_json()
    assert body["kind"] == "result" and body["result"]["status"] == "model_unavailable"
    assert body["result"]["planner_mode"] == "llm" and body["result"]["cost"] is None


def test_numbers_are_normalised_for_display():
    turn = chat.interpret("x", None, model_returning(
        {"budget": 40.0, "people": 2, "pantry": [{"ingredient": "rice", "quantity": 2.50, "unit": "lb"}]}))
    assert turn["request"]["budget"] == "40" and turn["request"]["pantry"][0]["quantity"] == "2.5"


def test_new_plan_note_only_when_something_was_discarded():
    first = chat.interpret("x", None, model_returning({"starts_new_request": True, "budget": 10, "people": 1}))
    assert "Started a new plan." not in first["notes"]
    again = chat.interpret("x", first["pending"], model_returning({"starts_new_request": True, "people": 4}))
    assert "Started a new plan." in again["notes"]


def test_high_protein_wording_maps_to_the_supported_preference():
    turn = chat.interpret("x", None, model_returning({
        "budget": 30, "people": 1, "dietary_preferences": ["High-Protein", "vegan"],
        "dietary_preferences_stated": True}))
    assert turn["kind"] == "ready"
    assert turn["request"]["dietary_preferences"] == ["high_protein", "vegan"]
