"""
Routers for item-related endpoints in the Grocery Saver API.

This module provides FastAPI routes to:
- List items with filtering, pagination, and sorting.
- Get a single item by ID.
- Bulk upsert items from a payload.
- Upsert a single item.
- Search items by name.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.repository.manager import repo_manager

router = APIRouter()

# Create tables if not exist (dev convenience)
Base.metadata.create_all(bind=engine)


@router.get("/")
def list_items(
    store_id: Optional[str] = Query(
        None,
        description="Filter by store ID",
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of items to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of items to skip",
    ),
    sort: str = Query(
        "last_seen_time",
        description=("Sort by: last_seen_time, name, price, promo_price"),
    ),
    order: str = Query(
        "desc",
        description="Sort order: asc or desc",
    ),
    db: Session = Depends(get_db),
):
    """
    List items with filtering and pagination.
    """
    repo_manager.initialize(db)

    items = repo_manager.list_items(
        store_id=store_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total": len(items),
        "ts": datetime.utcnow().isoformat(),
    }


@router.get("/search")
def search_items(
    q: str = Query(..., description="Search query"),
    store_id: Optional[str] = Query(
        None,
        description="Filter by store ID",
    ),
    db: Session = Depends(get_db),
):
    """
    Search items by name.
    """
    repo_manager.initialize(db)

    items = repo_manager.search_items(q, store_id)
    return {
        "items": items,
        "query": q,
        "store_id": store_id,
        "count": len(items),
        "ts": datetime.utcnow().isoformat(),
    }


@router.get("/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)):
    """
    Get item by ID.
    """
    repo_manager.initialize(db)

    item = repo_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


@router.post("/bulk_upsert")
def bulk_upsert(payload: dict, db: Session = Depends(get_db)):
    """
    Bulk UPSERT items from payload.
    """
    items = payload.get("items", [])
    if not isinstance(items, list):
        return {"error": "items must be a list"}

    stmt = text(
        """
        INSERT INTO items (
            id, name, price, promotion_price,
            store_id, last_seen_time, category,
            active, external_id
        )
        VALUES (
            :id, :name, :price, :promotion_price,
            :store_id, :last_seen_time, :category,
            :active, :external_id
        )
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name,
            price=EXCLUDED.price,
            promotion_price=EXCLUDED.promotion_price,
            store_id=EXCLUDED.store_id,
            last_seen_time=EXCLUDED.last_seen_time,
            category=EXCLUDED.category,
            active=EXCLUDED.active,
            external_id=EXCLUDED.external_id
        """
    )

    for it in items:
        if not isinstance(it.get("last_seen_time"), str):
            it["last_seen_time"] = datetime.utcnow().isoformat()
        db.execute(stmt, it)

    db.commit()
    return {"upserted": len(items)}


@router.post("/")
def upsert_item(item_data: dict, db: Session = Depends(get_db)):
    """
    Upsert item (temporary in-memory storage for debugging).
    """
    repo_manager.initialize(db)

    required_fields = ["id", "name", "store_id"]
    for field in required_fields:
        if field not in item_data:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field}",
            )

    try:
        result = repo_manager.upsert_item(item_data)
        return {
            "success": True,
            "item": result,
            "ts": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upsert item: {str(e)}",
        ) from e  # ✅ 保留 traceback 链
