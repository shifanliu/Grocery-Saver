from typing import List, Dict, Optional, Any
from pathlib import Path
from sqlalchemy.orm import Session
from .base_repo import BaseRepository
from .config import RepositoryConfig
from .db_repo import create_repository


class RepositoryManager:
    """Manager for repository operations"""
    
    def __init__(self):
        self._repo: Optional[BaseRepository] = None
        self._initialized = False
    
    def initialize(self, db_session: Optional[Session] = None) -> None:
        """Initialize the repository based on configuration"""
        if self._initialized:
            return
        
        # Create repository based on configuration
        self._repo = create_repository(
            repo_type=RepositoryConfig.REPO_TYPE,
            db_session=db_session
        )
        
        # Load CSV data if in CSV mode
        if RepositoryConfig.is_csv_mode():
            csv_paths = RepositoryConfig.get_csv_paths()
            self._repo.load_csv(csv_paths)
        
        self._initialized = True
    
    def get_repository(self) -> BaseRepository:
        """Get the repository instance"""
        if not self._initialized:
            raise RuntimeError("Repository not initialized. Call initialize() first.")
        return self._repo
    
    def list_items(
        self, 
        store_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "last_seen_time",
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """List items with filtering and pagination"""
        return self.get_repository().list_items(
            store_id=store_id,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order
        )
    
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item by ID"""
        return self.get_repository().get_item(item_id)
    
    def search_items(self, q: str, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search items by name"""
        return self.get_repository().search_items(q, store_id)
    
    def list_stores(self) -> List[Dict[str, Any]]:
        """List all stores"""
        return self.get_repository().list_stores()
    
    def upsert_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert item"""
        return self.get_repository().upsert_item(item_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
        return self.get_repository().get_stats()


# Global repository manager instance
repo_manager = RepositoryManager()
