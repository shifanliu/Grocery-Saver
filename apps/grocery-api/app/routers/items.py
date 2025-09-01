from fastapi import APIRouter, Depends, Query, HTTPException
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
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    sort: str = Query("last_seen_time", description="Sort field: last_seen_time, name, price, promotion_price"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db),
):
    """
    List items with filtering and pagination
    
    - **store_id**: Filter by store ID
    - **limit**: Number of items to return (1-100)
    - **offset**: Number of items to skip
    - **sort**: Sort field (last_seen_time, name, price, promotion_price)
    - **order**: Sort order (asc, desc)
    """
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    items = repo_manager.list_items(
        store_id=store_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order
    )

    return {
        "items": items, 
        "limit": limit, 
        "offset": offset, 
        "total": len(items),
        "ts": datetime.utcnow().isoformat()
    }


@router.get("/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)):
    """
    Get item by ID
    
    Supports both formats:
    - Single ID: "100364490"
    - Store:ID format: "costco_business_delivery:100364490"
    """
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    item = repo_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

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


@router.post("")
def upsert_item(item_data: dict, db: Session = Depends(get_db)):
    """
    Upsert item (temporary in-memory storage for debugging)
    
    Required fields:
    - id: Item ID
    - name: Item name
    - store_id: Store ID
    
    Optional fields:
    - price: Item price
    - promotion_price: Promotion price
    - category: Item category
    - active: Item status (default: true)
    - last_seen_time: Last seen timestamp (default: current time)
    """
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    # Validate required fields
    required_fields = ["id", "name", "store_id"]
    for field in required_fields:
        if field not in item_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    try:
        result = repo_manager.upsert_item(item_data)
        return {
            "success": True,
            "item": result,
            "ts": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upsert item: {str(e)}")


@router.get("/search")
def search_items(
    q: str = Query(..., description="Search query"),
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    db: Session = Depends(get_db),
):
    """
    Search items by name
    
    - **q**: Search query (required)
    - **store_id**: Filter by store ID (optional)
    """
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    items = repo_manager.search_items(q, store_id)
    return {
        "items": items, 
        "query": q, 
        "store_id": store_id, 
        "count": len(items),
        "ts": datetime.utcnow().isoformat()
    }
