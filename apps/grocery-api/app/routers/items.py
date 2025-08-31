from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.database import get_db, engine
from app.models import Item, Store
from app.database import Base
from app.repository.manager import repo_manager

router = APIRouter()

# Create tables if not exist (dev convenience)
Base.metadata.create_all(bind=engine)


@router.get("")
def list_items(
    store_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("last_seen_time"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    items = repo_manager.list_items(
        store_id=store_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order
    )

    return {"items": items, "limit": limit, "offset": offset, "ts": datetime.utcnow()}


@router.get("/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)):
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    item = repo_manager.get_item(item_id)
    if not item:
        return {"error": "not found"}

    return item


@router.post("/bulk_upsert")
def bulk_upsert(payload: dict, db: Session = Depends(get_db)):
    """
    Accepts: {"items": [ {id,name,price,promotion_price,store_id,last_seen_time,category,active,external_id}, ... ]}
    Performs UPSERT by id.
    """
    items = payload.get("items", [])
    if not isinstance(items, list):
        return {"error": "items must be a list"}

    # raw SQL upsert for simplicity (works on Postgres)
    stmt = text("""
        INSERT INTO items (id, name, price, promotion_price, store_id, last_seen_time, category, active, external_id)
        VALUES (:id, :name, :price, :promotion_price, :store_id, :last_seen_time, :category, :active, :external_id)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name,
            price=EXCLUDED.price,
            promotion_price=EXCLUDED.promotion_price,
            store_id=EXCLUDED.store_id,
            last_seen_time=EXCLUDED.last_seen_time,
            category=EXCLUDED.category,
            active=EXCLUDED.active,
            external_id=EXCLUDED.external_id
    """)

    for it in items:
        if isinstance(it.get("last_seen_time"), str):
            pass
        else:
            it["last_seen_time"] = datetime.utcnow().isoformat()
        db.execute(stmt, it)

    db.commit()
    return {"upserted": len(items)}


@router.get("/search")
def search_items(
    q: str = Query(..., description="Search query"),
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    db: Session = Depends(get_db),
):
    """Search items by name"""
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    items = repo_manager.search_items(q, store_id)
    return {"items": items, "query": q, "store_id": store_id, "count": len(items)}
