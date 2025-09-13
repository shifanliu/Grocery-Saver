pytest_plugins = ["tests.conftest_db"]

from datetime import datetime

def test_list_items_default(client, seed_data):
    r = client.get("/items")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and len(data["items"]) == 2
    assert data["limit"] == 20
    assert data["offset"] == 0
    # 返回总数字段是当前页数量（实现如此）
    assert data["total"] == 2

def test_list_items_filter_sort_pagination(client, seed_data):
    # 指定 store_id
    r = client.get("/items", params={"store_id": "test_store", "sort": "name", "order": "asc"})
    assert r.status_code == 200
    names = [it["name"] for it in r.json()["items"]]
    assert names == ["Apple Juice", "Banana"]

    # 分页
    r1 = client.get("/items", params={"limit": 1, "offset": 0})
    r2 = client.get("/items", params={"limit": 1, "offset": 1})
    assert len(r1.json()["items"]) == 1
    assert len(r2.json()["items"]) == 1
    assert r1.json()["items"][0]["id"] != r2.json()["items"][0]["id"]

def test_get_item_ok(client, seed_data):
    r = client.get("/items/item_1")
    assert r.status_code == 200
    assert r.json()["name"] == "Apple Juice"

def test_get_item_not_found(client):
    r = client.get("/items/no_such_id")
    assert r.status_code == 404

def test_search_items(client, seed_data):
    r = client.get("/items/search", params={"q": "apple"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["items"][0]["id"] == "item_1"

def test_upsert_item_ok(client, seed_data):
    payload = {
        "id": "ux_1",
        "name": "Grapes",
        "store_id": "test_store",
        "price": 2.49,
        "promotion_price": 1.99,
        "category": "Fruits",
        "active": True,
        "last_seen_time": datetime.utcnow().isoformat(),
    }
    r = client.post("/items", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["item"]["id"] == "ux_1"


def test_upsert_item_missing_field(client):
    # 少必填字段：name
    payload = {"id": "bad_1", "store_id": "test_store"}
    r = client.post("/items", json=payload)
    assert r.status_code == 400
    assert "Missing required field" in r.json()["detail"]
