from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseRepository(ABC):
    """Abstract base class for data repositories"""

    @abstractmethod
    def load_csv(self, paths: List[Path]) -> None:
        """Load data from CSV files"""

    @abstractmethod
    def list_items(
        self,
        store_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "last_seen_time",
        order: str = "desc",
    ) -> List[Dict[str, Any]]:
        """List items with filtering and pagination"""

    @abstractmethod
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item by ID (supports both 'store:id' and single id formats)"""

    @abstractmethod
    def search_items(
        self, q: str, store_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search items by name"""

    @abstractmethod
    def list_stores(self) -> List[Dict[str, Any]]:
        """List all stores"""

    @abstractmethod
    def upsert_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert item"""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
