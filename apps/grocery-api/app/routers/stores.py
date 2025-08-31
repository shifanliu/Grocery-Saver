from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app.models import Store
from app.database import Base
from app.repository.manager import repo_manager

router = APIRouter()

# Create tables if not exist (dev convenience)
Base.metadata.create_all(bind=engine)


@router.get("")
def list_stores(db: Session = Depends(get_db)):
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    return repo_manager.list_stores()


@router.post("")
def create_store(store: dict, db: Session = Depends(get_db)):
    s = Store(id=store["id"], name=store["name"], location=store.get("location", ""))
    db.add(s)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get repository statistics"""
    # Initialize repository if needed
    repo_manager.initialize(db)
    
    return repo_manager.get_stats()
