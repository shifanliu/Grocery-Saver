"""Criteria 1, 3, 4, 5: the loop, with mocked HTTP and mocked model."""
import copy
import io
import json
import urllib.error
from datetime import date
from decimal import Decimal as D

import pytest

from mealplan import settings
from mealplan.cli import DEFAULT_FIXTURE
from mealplan.sources import ApiSource, FixtureSource, ServiceError
from mealplan.workflow import run

TODAY = date(2026, 10, 1)
REQ = {"budget": 60, "people": 2, "dietary_preferences": ["vegan"],
       "pantry": [{"ingredient": "onion", "quantity": 500, "unit": "g"}]}
TIGHT = {"budget": 15, "people": 4, "dietary_preferences": ["vegan"], "pantry": []}


class SpySource(FixtureSource):
    """Real-data snapshot fixture that records every row it returns."""

    def __init__(self, data=None):
        super().__init__(path=DEFAULT_FIXTURE, data=data)
        self.returned = {}

    def search(self, q):
        rows = super().search(q)
        self.returned.update({str(r["id"]): r for r in rows})
        return rows


def fixture_data(edit):
    data = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    edit(data)
    return data


# -- criterion 1 --------------------------------------------------------------

def test_success_uses_only_searched_ids_and_exact_prices():
    src = SpySource()
    res = run(REQ, src, today=TODAY)
    assert res["status"] == "success"
    assert res["cost"]["line_items"]
    for li in res["cost"]["line_items"]:
        row = src.returned[li["product_id"]]             # id came from a search result
        assert li["unit_price"] == D(str(row["price"]))  # price equals that record
        assert li["price_timestamp"] == row["last_seen_time"]
    assert res["data"]["mode"] == "fixture" and "2026-07-22" in res["data"]["label"]
    assert res["planner_mode"] == "deterministic"


def test_llm_choice_must_come_from_search_results():
    seen = {}

    def model(prompt):
        seen["prompt"] = prompt
        return json.dumps({"template_id": "bean_rice_bowl", "product_ids": {
            "rice": "5415", "beans": "171345", "tomatoes": "1959935", "onion": "699753"}})

    res = run(REQ, SpySource(), model_fn=model, today=TODAY)
    assert res["status"] == "success" and res["planner_mode"] == "llm"
    assert {li["product_id"] for li in res["cost"]["line_items"]} >= {"5415", "171345"}
    assert "5415" in seen["prompt"]


@pytest.mark.parametrize("answer", [
    '{"template_id": "caviar_tower", "product_ids": {}}',  # unknown template
    '{"template_id": "bean_rice_bowl", "product_ids": {"rice": "999999", '
    '"beans": "171345", "tomatoes": "1959935", "onion": "699753"}}',  # invented product
    "I would suggest rice and beans!",  # not JSON
])
def test_llm_invalid_output_is_rejected_not_used(answer):
    res = run(REQ, SpySource(), model_fn=lambda p: answer, today=TODAY)
    assert res["status"] == "model_unavailable" and res["cost"] is None
    assert "rejected" in res["message"]


# -- criterion 3 --------------------------------------------------------------

def test_over_budget_tries_distinct_alternatives_within_bound():
    res = run(TIGHT, SpySource(), today=TODAY)
    assert res["status"] == "over_budget"
    attempts = res["attempts"]
    assert len(attempts) == 1 + settings.MAX_ADJUSTMENTS
    sigs = [(a["template_id"], tuple(sorted(a["products"].items()))) for a in attempts]
    assert len(set(sigs)) == len(sigs)  # no repeated candidate
    assert all(a["status"] == "ok" and a["total"] > D("15") for a in attempts)
    assert res["cost"]["total"] == min(a["total"] for a in attempts)  # cheapest *tried*
    assert "not a claim" in res["message"]


def test_adjustment_recomputes_and_stops_when_within_budget():
    res = run({"budget": 40, "people": 2, "dietary_preferences": ["vegan"], "pantry": []},
              SpySource(), today=TODAY)
    assert res["status"] == "success"
    first, second = res["attempts"]
    assert first["total"] > D("40") >= second["total"]
    assert (first["template_id"], first["products"]) != (second["template_id"], second["products"])


def test_retry_bound_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ADJUSTMENTS", 1)
    res = run(TIGHT, SpySource(), today=TODAY)
    assert res["status"] == "over_budget" and len(res["attempts"]) == 2


# -- criterion 4 --------------------------------------------------------------

def test_empty_results_give_no_results():
    res = run(REQ, FixtureSource(data={"kind": "synthetic", "label": "empty", "items": []}),
              today=TODAY)
    assert res["status"] == "no_results" and res["cost"] is None and res["plan"] is None
    assert "no search results" in res["message"]


def test_missing_price_gives_unsupported_data():
    def drop_onion_prices(d):
        for r in d["items"]:
            if "onion" in r["name"].lower() or " rice" in r["name"].lower():
                r["price"] = None  # every vegan meal needs onion or rice

    res = run(REQ, FixtureSource(data=fixture_data(drop_onion_prices)), today=TODAY)
    assert res["status"] == "unsupported_data" and res["cost"] is None
    assert "onion" in res["message"]


def test_unknown_package_size_gives_unsupported_data():
    def unmap_onions(d):  # same rows under ids the catalog has never verified
        for r in d["items"]:
            if r["name"] in ("Yellow Onions, 10 lbs", "Sweet Onion, 10 lbs") or "Rice" in r["name"]:
                r["id"] = "new-" + r["id"]  # every vegan meal needs onion or rice

    res = run(REQ, FixtureSource(data=fixture_data(unmap_onions)), today=TODAY)
    assert res["status"] == "unsupported_data"
    assert "verified package size" in res["message"] and "onion" in res["message"]


def test_weight_priced_chicken_is_not_costed():
    # only the per-lb-priced "9 lb avg wt" style rows exist: they are not in the catalog
    def only_perlb_chicken(d):
        d["items"] = [r for r in d["items"] if r["id"] in ("47735", "14057")]

    res = run({"budget": 99, "people": 1, "dietary_preferences": [], "pantry": []},
              FixtureSource(data=fixture_data(only_perlb_chicken)), today=TODAY)
    assert res["status"] in ("no_results", "unsupported_data") and res["cost"] is None


@pytest.mark.parametrize("bad", [
    {"budget": 0, "people": 2}, {"budget": -5, "people": 2}, {"budget": "abc", "people": 2},
    {"budget": 50, "people": 0}, {"budget": 50, "people": 1.5}, {"budget": True, "people": 2},
    {"budget": 50, "people": 2, "dietary_preferences": ["gluten-free"]},
    {"budget": 50, "people": 2, "pantry": [{"ingredient": "rice", "quantity": 1, "unit": "cups"}]},
])
def test_invalid_requests_are_rejected(bad):
    res = run(bad, SpySource(), today=TODAY)
    assert res["status"] == "invalid_request" and res["attempts"] == []


# -- criterion 5 --------------------------------------------------------------

class FailingSource:
    mode, label = "api", "Grocery Saver API at http://test (forced failure)"

    def search(self, q):
        raise ServiceError("forced failure")


def test_forced_api_failure_is_clean_and_distinct_from_empty():
    original = copy.deepcopy(REQ)
    res = run(REQ, FailingSource(), today=TODAY)
    assert res["status"] == "service_unavailable" and res["status"] != "no_results"
    assert res["request"] == original and REQ == original
    assert res["data"]["mode"] == "api" and res["planner_mode"] == "deterministic"
    assert res["cost"] is None and res["plan"] is None


def test_forced_model_failure_is_clean_and_not_silently_replaced():
    original = copy.deepcopy(REQ)

    def boom(prompt):
        raise RuntimeError("quota exceeded")

    res = run(REQ, SpySource(), model_fn=boom, today=TODAY)
    assert res["status"] == "model_unavailable"
    assert res["request"] == original and REQ == original
    assert res["planner_mode"] == "llm" and res["data"]["mode"] == "fixture"
    assert res["cost"] is None  # no silent fall back to the deterministic planner
    assert "quota exceeded" in res["message"]


# mocked HTTP: patch urllib so ApiSource itself is exercised

class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.mark.parametrize("effect,expect", [
    (urllib.error.URLError("refused"), "unreachable"),
    (urllib.error.HTTPError("http://x", 500, "boom", {}, None), "HTTP 500"),
    (TimeoutError("timed out"), "unreachable"),
    (FakeResp(b"<html>not json"), "non-JSON"),
    (FakeResp(b'{"results": []}'), "unexpected shape"),
    (FakeResp(b'{"items": [{"name": "no id"}]}'), "unexpected response shape"),
])
def test_api_source_failures_map_to_service_unavailable(monkeypatch, effect, expect):
    def fake_urlopen(url, timeout=None):
        assert timeout and timeout > 0  # a timeout is always applied
        if isinstance(effect, BaseException):
            raise effect
        return effect

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    res = run(REQ, ApiSource("http://test"), today=TODAY)
    assert res["status"] == "service_unavailable" and expect in res["message"]


def test_api_source_happy_path_with_mocked_http(monkeypatch):
    rows = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))["items"]

    def fake_urlopen(url, timeout=None):
        q = url.split("q=")[1].split("&")[0].replace("+", " ")
        hits = [r for r in rows if q in r["name"].lower()]
        return FakeResp(json.dumps({"items": hits, "count": len(hits)}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    res = run(REQ, ApiSource("http://test"), today=TODAY)
    assert res["status"] == "success" and res["data"]["mode"] == "api"


def test_stale_data_is_flagged_and_synthetic_is_labelled():
    res = run(REQ, SpySource(), today=date(2026, 10, 1))
    assert any("days old" in w for w in res["data"]["warnings"])
    synth = FixtureSource(data={"kind": "synthetic", "label": "toy", "items": []})
    assert synth.label.startswith("SAMPLE DATA (synthetic)")


def test_llm_prompt_lists_only_allowed_ids_with_prices_and_attempts():
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return json.dumps({"template_id": "bean_rice_bowl", "product_ids": {
            "rice": "841930", "beans": "171345", "tomatoes": "1959935", "onion": "699753"}})

    run(TIGHT, SpySource(), model_fn=model, today=TODAY)
    assert '"price": "25.29"' in prompts[0]               # prices shown, from search results
    assert "47735" not in prompts[0]                      # unmapped per-lb chicken never offered
    assert len(prompts) <= 1 + settings.MAX_ADJUSTMENTS   # bounded model calls
    assert len(prompts) == 2  # the repeated choice is detected as "nothing new" and the loop stops


# -- fitness (high_protein) templates -----------------------------------------

def test_high_protein_tag_matches_the_protein_estimate():
    from mealplan import catalog
    fitness = [t for t in catalog.TEMPLATES if "high_protein" in t.tags]
    assert len(fitness) == 6
    for t in catalog.TEMPLATES:
        assert ("high_protein" in t.tags) == (t.est_protein_g >= catalog.HIGH_PROTEIN_MIN_G), t.id
        assert all(i in catalog.SEARCH_TERMS for i in t.ingredients)  # every ingredient is searchable


@pytest.mark.parametrize("prefs,allowed_tags", [
    (["high_protein"], {"high_protein"}),
    (["vegan", "high_protein"], {"vegan", "high_protein"}),
    (["vegetarian", "high_protein"], {"vegetarian", "high_protein"}),
])
def test_high_protein_requests_only_use_tagged_templates(prefs, allowed_tags):
    from mealplan import catalog
    res = run({"budget": 80, "people": 1, "dietary_preferences": prefs, "pantry": []},
              SpySource(), today=TODAY)
    assert res["status"] == "success"
    tags = set(res["plan"]["tags"])
    assert allowed_tags <= tags and res["plan"]["est_protein_g_per_serving"] >= 30
    assert all(a["template_id"] in {t.id for t in catalog.eligible_templates(prefs)}
               for a in res["attempts"])


def test_vegan_high_protein_never_includes_eggs_or_chicken():
    res = run({"budget": 10, "people": 2, "dietary_preferences": ["vegan", "high_protein"], "pantry": []},
              SpySource(), today=TODAY)  # tight budget forces all adjustments
    ids = {li["ingredient"] for li in res["cost"]["line_items"]}
    assert not ids & {"eggs", "chicken"}
    assert all(a["template_id"] in ("tofu_rice_power_bowl", "tofu_bean_scramble") for a in res["attempts"])


def test_oats_come_from_search_results_and_whole_packages():
    res = run({"budget": 30, "people": 2, "dietary_preferences": ["vegetarian", "high_protein"],
               "pantry": [{"ingredient": "eggs", "quantity": 2, "unit": "dozen"}]},
              SpySource(), today=TODAY)
    assert res["status"] == "success"
    oats = [li for li in res["cost"]["line_items"] if li["ingredient"] == "oats"]
    if oats:  # whichever meal won, oats are priced by whole packages from the search rows
        assert oats[0]["product_id"] in ("446586", "731962") and oats[0]["packages_needed"] >= 1
