"""
Test configuration and fixtures for grocery-api tests
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app=app)


@pytest.fixture
def mock_repo_manager():
    """Mock repository manager fixture"""
    with patch('app.routers.items.repo_manager') as mock_manager:
        # Setup default mock behavior
        mock_manager.initialize.return_value = None
        mock_manager.list_items.return_value = []
        mock_manager.get_item.return_value = None
        mock_manager.search_items.return_value = []
        mock_manager.upsert_item.return_value = {}
        mock_manager.list_stores.return_value = []
        mock_manager.get_stats.return_value = {
            "items": 0,
            "stores": 0,
            "loaded": False,
            "store_counts": {}
        }
        yield mock_manager


@pytest.fixture
def sample_item():
    """Sample item data fixture"""
    return {
        "id": "100364490",
        "name": "Kirkland Signature Wildflower Honey, 5 lbs",
        "price": 14.79,
        "promotion_price": 14.79,
        "store_id": "costco_business_delivery",
        "last_seen_time": "2025-08-25T23:56:25Z",
        "category": "Baking",
        "active": True
    }


@pytest.fixture
def sample_store():
    """Sample store data fixture"""
    return {
        "id": "costco_business_delivery",
        "name": "Costco Business Delivery",
        "location": ""
    }


@pytest.fixture
def sample_items_list(sample_item):
    """Sample items list fixture"""
    return [sample_item]


@pytest.fixture
def sample_stores_list(sample_store):
    """Sample stores list fixture"""
    return [
        sample_store,
        {
            "id": "3132",
            "name": "Safeway",
            "location": ""
        }
    ]


@pytest.fixture
def sample_stats():
    """Sample stats data fixture"""
    return {
        "items": 3365,
        "stores": 2,
        "loaded": True,
        "store_counts": {
            "costco_business_delivery": 824,
            "3132": 2541
        }
    }
