pytest_plugins = ["tests.conftest_db"]

def test_list_stores(client, seed_data):
    r = client.get("/stores")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    ids = {s["id"] for s in data["stores"]}
    assert "test_store" in ids

def test_create_store(client):
    payload = {"id": "s2", "name": "Another Store", "location": "Sacramento, CA"}
    r = client.post("/stores", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_stats(client, seed_data):
    r = client.get("/stores/stats")
    assert r.status_code == 200
    stats = r.json()
    assert stats["items"] >= 2
    assert stats["stores"] >= 1
    assert stats["loaded"] is True
    assert "store_counts" in stats
