"""
Routers for store-related endpoints in the Grocery Saver API.

This module provides FastAPI routes to:
- List all stores.
- Create a new store.
- Get repository statistics.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Store
from app.repository.manager import repo_manager

router = APIRouter()

# Create tables if not exist (dev convenience)
Base.metadata.create_all(bind=engine)


@router.get("/")
def list_stores(db: Session = Depends(get_db)):
    """
    List all stores.

    Returns a list of all available stores with their basic information.
    """
    repo_manager.initialize(db)
    stores = repo_manager.list_stores()
    return {
        "stores": stores,
        "count": len(stores),
        "ts": datetime.utcnow().isoformat(),
    }


@router.post("/")
def create_store(store: dict, db: Session = Depends(get_db)):
    """
    Create a new store.

    Args:
        store (dict): Store data with keys 'id',
        'name', and optional 'location'.

    Returns:
        dict: Confirmation of success.
    """
    s = Store(
        id=store["id"], name=store["name"], location=store.get("location", "")
    )
    db.add(s)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Get repository statistics.

    Returns comprehensive statistics about the repository including:
    - Total number of items and stores
    - Item counts per store
    - Repository status
    """
    repo_manager.initialize(db)
    stats = repo_manager.get_stats()
    return {**stats, "ts": datetime.utcnow().isoformat()}
