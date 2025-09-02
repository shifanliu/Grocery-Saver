from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Store
from app.repository.manager import repo_manager

router = APIRouter()

# Create tables if not exist (dev convenience)
Base.metadata.create_all(bind=engine)


@router.get("")
def list_stores(db: Session = Depends(get_db)):
    """
    List all stores

    Returns a list of all available stores with their basic information.
    """
    # Initialize repository if needed
    repo_manager.initialize(db)

    stores = repo_manager.list_stores()
    return {"stores": stores, "count": len(stores), "ts": datetime.utcnow().isoformat()}


@router.post("")
def create_store(store: dict, db: Session = Depends(get_db)):
    s = Store(id=store["id"], name=store["name"], location=store.get("location", ""))
    db.add(s)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Get repository statistics

    Returns comprehensive statistics about the repository including:
    - Total number of items and stores
    - Item counts per store
    - Repository status
    """
    # Initialize repository if needed
    repo_manager.initialize(db)

    stats = repo_manager.get_stats()
    return {**stats, "ts": datetime.utcnow().isoformat()}
