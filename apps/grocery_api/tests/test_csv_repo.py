#!/usr/bin/env python3
"""
Test script for CSV repository functionality
"""

import sys
from pathlib import Path
import os
import pytest

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.repository.manager import repo_manager
from app.repository.config import RepositoryConfig

if os.getenv("REPO_TYPE", "csv") == "db":
    pytest.skip("Skipping CSV repo tests in DB mode", allow_module_level=True)


def test_csv_repository():
    """Test CSV repository functionality"""
    print("Testing CSV Repository...")
    print("=" * 50)
    
    # Initialize repository
    print("Initializing repository...")
    repo_manager.initialize()
    
    # Test stats
    print("\n1. Repository Statistics:")
    stats = repo_manager.get_stats()
    print(f"   Items: {stats['items']}")
    print(f"   Stores: {stats['stores']}")
    print(f"   Store counts: {stats['store_counts']}")
    
    # Test list stores
    print("\n2. List Stores:")
    stores = repo_manager.list_stores()
    for store in stores:
        print(f"   - {store['id']}: {store['name']}")
    
    # Test list items
    print("\n3. List Items (first 5):")
    items = repo_manager.list_items(limit=5)
    for item in items:
        print(f"   - {item['id']}: {item['name']} (${item['price']})")
    
    # Test list items by store
    print("\n4. List Items by Store (Costco, first 3):")
    costco_items = repo_manager.list_items(store_id="costco_business_delivery", limit=3)
    for item in costco_items:
        print(f"   - {item['id']}: {item['name']} (${item['price']})")
    
    # Test search
    print("\n5. Search Items ('honey'):")
    honey_items = repo_manager.search_items("honey")
    for item in honey_items[:3]:  # Show first 3
        print(f"   - {item['id']}: {item['name']} (${item['price']})")
    print(f"   Total found: {len(honey_items)}")
    
    # Test get item
    print("\n6. Get Item by ID:")
    if items:
        first_item_id = items[0]['id']
        item = repo_manager.get_item(first_item_id)
        if item:
            print(f"   Found: {item['name']} (${item['price']})")
    
    # Test get item with store:id format
    print("\n7. Get Item by Store:ID format:")
    if costco_items:
        first_costco_item = costco_items[0]
        store_item_id = f"{first_costco_item['store_id']}:{first_costco_item['id']}"
        item = repo_manager.get_item(store_item_id)
        if item:
            print(f"   Found: {item['name']} (${item['price']})")
    
    # Test upsert item
    print("\n8. Test Upsert Item:")
    test_item = {
        "id": "test_item_001",
        "name": "Test Product",
        "price": 9.99,
        "promotion_price": 7.99,
        "store_id": "test_store",
        "category": "Test Category",
        "active": True
    }
    upserted = repo_manager.upsert_item(test_item)
    print(f"   Upserted: {upserted['name']} (${upserted['price']})")
    
    # Verify the item was added
    retrieved = repo_manager.get_item("test_item_001")
    if retrieved:
        print(f"   Retrieved: {retrieved['name']} (${retrieved['price']})")
    
    print("\n" + "=" * 50)
    print("CSV Repository test completed successfully!")


if __name__ == "__main__":
    test_csv_repository()
