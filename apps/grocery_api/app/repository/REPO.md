# Repository Layer

This repository layer provides a unified data access interface, supporting loading data from CSV files into memory, with easy switching to a database implementation.

## Design Goals

1. **Unified Interface**: Provide consistent method signatures regardless of whether the underlying storage is CSV or a database.  
2. **Easy Switching**: Switch between CSV and database via configuration.  
3. **In-Memory Storage**: Load CSV data into memory for fast queries.  
4. **Debug-Friendly**: Support temporary in-memory writes for easier debugging.  

## Core Components

### 1. BaseRepository (Abstract Base Class)
Defines a unified data access interface:
- `load_csv(paths)` – Load CSV files  
- `list_items()` – List items (supports pagination, sorting, filtering)  
- `get_item(item_id)` – Get a single item (supports `store:id` format)  
- `search_items(q, store_id)` – Search items  
- `list_stores()` – List stores  
- `upsert_item(item)` – Update or insert item  
- `get_stats()` – Get statistics  

### 2. CSVRepository (CSV Implementation)
- Loads data from CSV files into memory  
- Provides fast in-memory queries  
- Supports temporary writes (for debugging)  
- Automatically infers store names  

### 3. DatabaseRepository (Database Implementation)
- Uses SQLAlchemy for database operations  
- Implements the same interface  
- Supports transactions and persistent storage  

### 4. RepositoryManager (Manager)
- Unified entry point  
- Automatically selects implementation based on configuration  
- Handles initialization logic  

## Usage

### Basic Usage

```python
from app.repository.manager import repo_manager

# Initialize (will automatically load CSV data)
repo_manager.initialize()

# List items
items = repo_manager.list_items(limit=10, store_id="costco_business_delivery")

# Search items
results = repo_manager.search_items("honey")

# Get a single item
item = repo_manager.get_item("100364490")
# Or use store:id format
item = repo_manager.get_item("costco_business_delivery:100364490")

# List stores
stores = repo_manager.list_stores()

# Get statistics
stats = repo_manager.get_stats()
```

### Configuration

Control the repository type using environment variables:

```bash
# Use CSV mode (default)
export REPO_TYPE=csv

# Use database mode
export REPO_TYPE=db
```

### CSV File Path Configuration

Configure CSV file paths in `config.py`:

```python
CSV_PATHS = [
    Path("apps/grocery_collector/costco_items.csv"),
    Path("apps/grocery_collector/safeway_items.csv"),
]
```

## API Endpoints

### Item Related
- `GET /items` - List items (supports pagination, sorting, filtering)  
- `GET /items/{item_id}` - Get a single item  
- `GET /items/search?q={query}` - Search items  
- `POST /items/bulk_upsert` - Bulk update items  

### Store Related
- `GET /stores` - List stores  
- `GET /stores/stats` - Get statistics  

## Data Format

### Item Data
```json
{
  "id": "100364490",
  "name": "Kirkland Signature Wildflower Honey, 5 lbs",
  "price": 14.79,
  "promotion_price": 14.79,
  "store_id": "costco_business_delivery",
  "last_seen_time": "2025-08-25T23:56:25Z",
  "category": "Baking",
  "active": true
}
```

### Store Data
```json
{
  "id": "costco_business_delivery",
  "name": "Costco Business Delivery",
  "location": ""
}
```

## Testing

Run the test script to verify functionality:

```bash
cd apps/grocery-api
python test_csv_repo.py
```

## Extensions

### Adding a New Data Source

1. Inherit from `BaseRepository`  
2. Implement all abstract methods  
3. Add the new type in the `create_repository()` factory function  
4. Update configuration  

### Adding a New Query Method

1. Add an abstract method in `BaseRepository`  
2. Implement it in all subclasses  
3. Add a proxy method in `RepositoryManager`  
4. Add the corresponding endpoint in routes  

## Performance Considerations

- CSV Mode: Data is loaded into memory, queries are fast, but memory usage is higher  
- Database Mode: Supports large datasets, but query speed is relatively slower  
- Recommendation: Use CSV mode for development/debugging, and database mode in production  
