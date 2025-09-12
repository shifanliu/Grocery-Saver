pytest_plugins = ["tests.conftest_db"]

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

def test_db_repo_crud_and_queries(db_session: Session, seed_data):
    from app.repository.db_repo import DatabaseRepository

    repo = DatabaseRepository(db_session)

    # list_stores
    stores = repo.list_stores()
    assert len(stores) == 1
    assert stores[0]["id"] == "test_store"

    items = repo.list_items()
    assert len(items) == 2
    assert items[0]["id"] in {"item_1", "item_2"}
    items_filtered = repo.list_items(store_id="test_store")
    assert len(items_filtered) == 2

    # 排序：按 name asc
    items_by_name = repo.list_items(sort="name", order="asc")
    assert [it["name"] for it in items_by_name] == ["Apple Juice", "Banana"]

    # 分页
    page1 = repo.list_items(limit=1, offset=0)
    page2 = repo.list_items(limit=1, offset=1)
    assert len(page1) == 1 and len(page2) == 1
    assert page1[0]["id"] != page2[0]["id"]

    # get_item by id
    got = repo.get_item("item_1")
    assert got and got["name"] == "Apple Juice"

    # get_item by store:id 格式
    got2 = repo.get_item("test_store:item_2")
    assert got2 and got2["name"] == "Banana"

    # search_items
    found = repo.search_items("apple")  # 不区分大小写
    assert len(found) == 1 and found[0]["id"] == "item_1"

    # upsert_item（新增）
    new_item = {
        "id": "item_3",
        "name": "Orange",
        "price": 0.99,
        "promotion_price": None,
        "store_id": "test_store",
        "last_seen_time": datetime.utcnow().isoformat(),
        "category": "Fruits",
        "active": True,
    }
    upserted_new = repo.upsert_item(new_item)
    assert upserted_new["id"] == "item_3"

    # upsert_item（更新）
    update_payload = {
        "id": "item_3",
        "name": "Orange (Navel)",
        "price": 1.19,
        "promotion_price": 0.89,
        "store_id": "test_store",
        "last_seen_time": datetime.utcnow().isoformat(),
        "category": "Fruits",
        "active": True,
    }
    upserted_update = repo.upsert_item(update_payload)
    assert upserted_update["name"].startswith("Orange")
    assert upserted_update["price"] == 1.19

    # stats
    stats = repo.get_stats()
    assert stats["items"] >= 3
    assert stats["stores"] == 1
    assert stats["loaded"] is True
    assert stats["store_counts"]["test_store"] >= 3
