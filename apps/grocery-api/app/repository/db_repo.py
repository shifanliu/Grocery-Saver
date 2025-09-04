"""
Database-backed repository implementation for the Grocery Saver API.

This module defines `DatabaseRepository`, a SQLAlchemy-based implementation
of the repository interface, and a small factory `create_repository` to
obtain either DB or CSV repository based on configuration.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Item as DBItem
from app.models import Store as DBStore

from .base_repo import BaseRepository
from .csv_repo import CSVRepository  # moved to top-level to avoid C0415


class DatabaseRepository(BaseRepository):
    """Database-based data repository for grocery items and stores."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def load_csv(self, paths: List[Path]) -> None:
        """Load data from CSV files into database (not implemented)."""
        # This would typically be used for initial data loading.
        # For now, we'll just note that data should already be in DB.
        print(
            "Database repo: CSV loading not implemented, data should be in DB"
        )

    def list_items(
        self,
        store_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "last_seen_time",
        order: str = "desc",
    ) -> List[Dict[str, Any]]:
        """List items with filtering and pagination."""
        valid_sort = {"last_seen_time", "name", "price", "promotion_price"}
        sort_field = sort if sort in valid_sort else "last_seen_time"
        order_kw = "desc" if order.lower() == "desc" else "asc"

        q = self.db.query(DBItem)
        if store_id:
            q = q.filter(DBItem.store_id == store_id)

        q = (
            q.order_by(text(f"{sort_field} {order_kw}"))
            .offset(offset)
            .limit(limit)
        )

        return [
            {
                "id": i.id,
                "name": i.name,
                "price": i.price,
                "promotion_price": i.promotion_price,
                "store_id": i.store_id,
                "last_seen_time": i.last_seen_time.isoformat(),
                "category": i.category,
                "active": i.active,
            }
            for i in q.all()
        ]

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item by ID (supports both 'store:id' and single id formats)."""
        # Handle 'store:id' format
        if ":" in item_id:
            store_id, item_id = item_id.split(":", 1)
            item = (
                self.db.query(DBItem)
                .filter(DBItem.id == item_id, DBItem.store_id == store_id)
                .first()
            )
        else:
            item = self.db.get(DBItem, item_id)

        if not item:
            return None

        return {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "promotion_price": item.promotion_price,
            "store_id": item.store_id,
            "last_seen_time": item.last_seen_time.isoformat(),
            "category": item.category,
            "active": item.active,
        }

    def search_items(
        self, q: str, store_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search items by name (case-insensitive)."""
        query = self.db.query(DBItem).filter(DBItem.name.ilike(f"%{q}%"))
        if store_id:
            query = query.filter(DBItem.store_id == store_id)

        items = query.all()
        return [
            {
                "id": item.id,
                "name": item.name,
                "price": item.price,
                "promotion_price": item.promotion_price,
                "store_id": item.store_id,
                "last_seen_time": item.last_seen_time.isoformat(),
                "category": item.category,
                "active": item.active,
            }
            for item in items
        ]

    def list_stores(self) -> List[Dict[str, Any]]:
        """List all stores."""
        stores = self.db.query(DBStore).all()
        return [
            {"id": s.id, "name": s.name, "location": s.location}
            for s in stores
        ]

    def upsert_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert item using database."""
        # Check if item exists
        existing_item = self.db.get(DBItem, item_data["id"])

        if existing_item:
            # Update existing item
            existing_item.name = item_data["name"]
            existing_item.price = item_data.get("price")
            existing_item.promotion_price = item_data.get("promotion_price")
            existing_item.store_id = item_data["store_id"]
            existing_item.last_seen_time = datetime.fromisoformat(
                item_data.get("last_seen_time", datetime.utcnow().isoformat())
            )
            existing_item.category = item_data.get("category", "")
            existing_item.active = item_data.get("active", True)
            item = existing_item
        else:
            # Create new item
            item = DBItem(
                id=item_data["id"],
                name=item_data["name"],
                price=item_data.get("price"),
                promotion_price=item_data.get("promotion_price"),
                store_id=item_data["store_id"],
                last_seen_time=datetime.fromisoformat(
                    item_data.get(
                        "last_seen_time", datetime.utcnow().isoformat()
                    )
                ),
                category=item_data.get("category", ""),
                active=item_data.get("active", True),
            )
            self.db.add(item)

        self.db.commit()

        return {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "promotion_price": item.promotion_price,
            "store_id": item.store_id,
            "last_seen_time": item.last_seen_time.isoformat(),
            "category": item.category,
            "active": item.active,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        item_count = self.db.query(DBItem).count()
        store_count = self.db.query(DBStore).count()

        # Get item counts by store
        store_counts: Dict[str, int] = {}
        stores = self.db.query(DBStore).all()
        for store in stores:
            count = (
                self.db.query(DBItem)
                .filter(DBItem.store_id == store.id)
                .count()
            )
            store_counts[store.id] = count

        return {
            "items": item_count,
            "stores": store_count,
            "loaded": True,
            "store_counts": store_counts,
        }


# Factory function to create repository based on configuration
def create_repository(
    repo_type: str = "csv", db_session: Optional[Session] = None
) -> BaseRepository:
    """Factory function to create appropriate repository."""
    if repo_type == "db":
        if not db_session:
            raise ValueError("Database session required for DB repository")
        return DatabaseRepository(db_session)
    # no-else-return: fall through to CSV as default
    return CSVRepository()
