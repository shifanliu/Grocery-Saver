"""
Tests for the /planner proxy and the product detail page. The agent service is
mocked at the HTTP layer; no model or real service is called.
"""

import io
import json
import urllib.error

import pytest

pytest_plugins = ["tests.conftest_db"]

GOOD_PLAN = {
    "budget": 40,
    "people": 2,
    "dietary_preferences": ["vegan"],
    "pantry": [{"ingredient": "Onion", "quantity": 500, "unit": "g"}],
}


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def agent_result(product_id="item_1", store_id="test_store"):
    return {
        "kind": "result",
        "result": {
            "status": "success",
            "cost": {
                "total": "9.50",
                "line_items": [
                    {"product_id": product_id, "store_id": store_id,
                     "product_name": "Apple Juice", "packages_needed": 1,
                     "unit_price": "9.50", "line_total": "9.50"},
                    {"product_id": "ghost", "store_id": store_id,
                     "product_name": "Not in DB", "packages_needed": 1,
                     "unit_price": "1.00", "line_total": "1.00"},
                ],
            },
        },
    }


@pytest.fixture
def agent(monkeypatch):
    """Capture what is sent to the agent and let each test choose the reply."""
    sent = {}

    def install(reply=None, error=None):
        def fake_urlopen(req, timeout=None):
            sent["url"] = req.full_url
            sent["body"] = json.loads(req.data.decode())
            sent["timeout"] = timeout
            if error:
                raise error
            return FakeResp(json.dumps(reply).encode())

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return sent

    return install


def test_plan_forwards_validated_request_and_links_only_real_products(client, seed_data, agent):
    sent = agent(agent_result())
    r = client.post("/planner/plan", json=GOOD_PLAN)
    assert r.status_code == 200
    assert sent["url"].endswith("/plan") and sent["timeout"] > 0
    assert sent["body"]["request"] == {
        "budget": "40", "people": 2, "dietary_preferences": ["vegan"],
        "pantry": [{"ingredient": "onion", "quantity": "500", "unit": "g"}]}
    items = r.json()["result"]["cost"]["line_items"]
    assert items[0]["product_url"] == "/products/test_store:item_1"
    assert items[0]["retailer_url"] is None          # never invented
    assert items[1]["product_url"] is None           # unknown id gets no link
    page = client.get(items[0]["product_url"])
    assert page.status_code == 200 and "Apple Juice" in page.text


@pytest.mark.parametrize("patch", [
    {"budget": 0}, {"budget": -3}, {"budget": "abc"}, {"people": 0}, {"people": 1.5},
    {"dietary_preferences": ["keto"]}, {"pantry": [{"ingredient": "rice", "quantity": 1, "unit": "cups"}]},
    {"pantry": [{"ingredient": "rice", "quantity": -1, "unit": "g"}]}, {"planner": "magic"},
])
def test_plan_rejects_invalid_input_before_forwarding(client, agent, patch):
    sent = agent({})
    r = client.post("/planner/plan", json={**GOOD_PLAN, **patch})
    assert r.status_code == 422 and "url" not in sent


def test_chat_forwards_message_and_pending(client, seed_data, agent):
    sent = agent({"kind": "ask", "message": "How many people?", "pending": {"budget": "40"}})
    r = client.post("/planner/chat", json={"message": "under $40", "pending": {"budget": "40"}})
    assert r.status_code == 200 and r.json()["kind"] == "ask"
    assert sent["body"] == {"message": "under $40", "pending": {"budget": "40"}, "planner": "deterministic"}


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 501}, {"message": 5}])
def test_chat_rejects_bad_messages(client, agent, payload):
    agent({})
    assert client.post("/planner/chat", json=payload).status_code == 422


@pytest.mark.parametrize("error,status,text", [
    (urllib.error.URLError("refused"), 503, "not reachable"),
    (TimeoutError("slow"), 504, "did not answer"),
    (urllib.error.HTTPError("http://x", 500, "boom", {}, None), 502, "HTTP 500"),
])
def test_agent_failures_become_readable_errors(client, agent, error, status, text):
    agent(error=error)
    r = client.post("/planner/chat", json={"message": "hello"})
    assert r.status_code == status and text in r.json()["detail"]


def test_non_json_agent_reply_is_a_502(client, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeResp(b"<html>"))
    r = client.post("/planner/chat", json={"message": "hello"})
    assert r.status_code == 502


def test_product_page_found_and_not_found(client, seed_data):
    ok = client.get("/products/test_store:item_1")
    assert ok.status_code == 200 and "Apple Juice" in ok.text
    assert client.get("/products/test_store:nope").status_code == 404


def test_product_page_escapes_html(client, db_session, seed_data):
    from app.models import Item
    from datetime import datetime
    db_session.add(Item(id="xss", name="<script>alert(1)</script>", price=1.0, promotion_price=None,
                        store_id="test_store", last_seen_time=datetime.utcnow(), category="c", active=True))
    db_session.commit()
    page = client.get("/products/test_store:xss")
    assert "<script>alert(1)</script>" not in page.text and "&lt;script&gt;" in page.text
