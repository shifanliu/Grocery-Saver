import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_repo import BaseRepository


@dataclass
class Item:
    id: str
    name: str
    price: Optional[float]
    promotion_price: Optional[float]
    store_id: str
    last_seen_time: datetime
    category: str
    active: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "promotion_price": self.promotion_price,
            "store_id": self.store_id,
            "last_seen_time": self.last_seen_time.isoformat(),
            "category": self.category,
            "active": self.active,
        }


@dataclass
class Store:
    id: str
    name: str
    location: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
        }


class CSVRepository(BaseRepository):
    """CSV-based data repository for grocery items and stores"""

    def __init__(self):
        self._items: Dict[str, Item] = {}  # id -> Item
        self._stores: Dict[str, Store] = {}  # id -> Store
        self._loaded = False

    def load_csv(self, paths: List[Path]) -> None:
        """Load data from multiple CSV files into memory"""
        self._items.clear()
        self._stores.clear()

        for path in paths:
            if not path.exists():
                print(f"Warning: CSV file not found: {path}")
                continue

            print(f"Loading CSV: {path}")
            self._load_single_csv(path)

        self._loaded = True
        print(f"Loaded {len(self._items)} items and {len(self._stores)} stores")

    def _load_single_csv(self, path: Path) -> None:
        """Load data from a single CSV file"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Parse item data
                    item = self._parse_item_row(row)
                    if item:
                        self._items[item.id] = item

                        # Auto-create store if not exists
                        if item.store_id not in self._stores:
                            store_name = self._infer_store_name(item.store_id)
                            self._stores[item.store_id] = Store(
                                id=item.store_id, name=store_name, location=""
                            )

        except Exception as e:
            print(f"Error loading CSV {path}: {e}")

    def _parse_item_row(self, row: Dict[str, str]) -> Optional[Item]:
        """Parse a CSV row into an Item object"""
        try:
            # Parse price fields
            price = self._parse_float(row.get("price"))
            promotion_price = self._parse_float(row.get("promotion_price"))

            # Parse datetime
            last_seen_time = self._parse_datetime(row.get("last_seen_time"))

            # Parse boolean
            active = row.get("active", "True").lower() == "true"

            return Item(
                id=row["id"],
                name=row["name"],
                price=price,
                promotion_price=promotion_price,
                store_id=row["store_id"],
                last_seen_time=last_seen_time,
                category=row.get("category", ""),
                active=active,
            )
        except Exception as e:
            print(f"Error parsing row {row.get('id', 'unknown')}: {e}")
            return None

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float value, return None if empty or invalid"""
        if not value or value.strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_datetime(self, value: Optional[str]) -> datetime:
        """Parse datetime string, return current time if invalid"""
        if not value:
            return datetime.utcnow()
        try:
            # Handle ISO format with Z suffix
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.utcnow()

    def _infer_store_name(self, store_id: str) -> str:
        """Infer store name from store_id"""
        if store_id == "costco_business_delivery":
            return "Costco Business Delivery"
        elif store_id == "3132":
            return "Safeway"
        else:
            return store_id.replace("_", " ").title()

    def list_items(
        self,
        store_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "last_seen_time",
        order: str = "desc",
    ) -> List[Dict[str, Any]]:
        """List items with filtering and pagination"""
        if not self._loaded:
            return []

        # Filter by store_id if specified
        items = list(self._items.values())
        if store_id:
            items = [item for item in items if item.store_id == store_id]

        # Sort items
        reverse = order.lower() == "desc"
        if sort == "name":
            items.sort(key=lambda x: x.name.lower(), reverse=reverse)
        elif sort == "price":
            items.sort(key=lambda x: (x.price or 0), reverse=reverse)
        elif sort == "promotion_price":
            items.sort(key=lambda x: (x.promotion_price or 0), reverse=reverse)
        else:  # default: last_seen_time
            items.sort(key=lambda x: x.last_seen_time, reverse=reverse)

        # Apply pagination
        items = items[offset : offset + limit]

        return [item.to_dict() for item in items]

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item by ID (supports both 'store:id' and single id formats)"""
        if not self._loaded:
            return None

        # Handle 'store:id' format
        if ":" in item_id:
            store_id, item_id = item_id.split(":", 1)
            item = self._items.get(item_id)
            if item and item.store_id == store_id:
                return item.to_dict()
            return None

        # Handle single id format
        item = self._items.get(item_id)
        return item.to_dict() if item else None

    def search_items(
        self, q: str, store_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search items by name (case-insensitive)"""
        if not self._loaded:
            return []

        q_lower = q.lower()
        results = []

        for item in self._items.values():
            # Filter by store_id if specified
            if store_id and item.store_id != store_id:
                continue

            # Search in name
            if q_lower in item.name.lower():
                results.append(item.to_dict())

        return results

    def list_stores(self) -> List[Dict[str, Any]]:
        """List all stores"""
        if not self._loaded:
            return []

        return [store.to_dict() for store in self._stores.values()]

    def upsert_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert item (temporary in-memory storage for debugging)"""
        # Parse the item data
        item = Item(
            id=item_data["id"],
            name=item_data["name"],
            price=self._parse_float(str(item_data.get("price", ""))),
            promotion_price=self._parse_float(
                str(item_data.get("promotion_price", ""))
            ),
            store_id=item_data["store_id"],
            last_seen_time=self._parse_datetime(item_data.get("last_seen_time")),
            category=item_data.get("category", ""),
            active=item_data.get("active", True),
        )

        # Store in memory
        self._items[item.id] = item

        # Auto-create store if not exists
        if item.store_id not in self._stores:
            store_name = self._infer_store_name(item.store_id)
            self._stores[item.store_id] = Store(
                id=item.store_id, name=store_name, location=""
            )

        return item.to_dict()

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
        if not self._loaded:
            return {"items": 0, "stores": 0, "loaded": False}

        return {
            "items": len(self._items),
            "stores": len(self._stores),
            "loaded": True,
            "store_counts": {
                store_id: len(
                    [item for item in self._items.values() if item.store_id == store_id]
                )
                for store_id in self._stores.keys()
            },
        }


# Global repository instance
csv_repo = CSVRepository()
