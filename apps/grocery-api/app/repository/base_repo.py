from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pathlib import Path


class BaseRepository(ABC):
    """Abstract base class for data repositories"""
    
    @abstractmethod
    def load_csv(self, paths: List[Path]) -> None:
        """Load data from CSV files"""
        pass
    
    @abstractmethod
    def list_items(
        self, 
        store_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "last_seen_time",
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """List items with filtering and pagination"""
        pass
    
    @abstractmethod
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item by ID (supports both 'store:id' and single id formats)"""
        pass
    
    @abstractmethod
    def search_items(self, q: str, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search items by name"""
        pass
    
    @abstractmethod
    def list_stores(self) -> List[Dict[str, Any]]:
        """List all stores"""
        pass
    
    @abstractmethod
    def upsert_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert item"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
        pass
