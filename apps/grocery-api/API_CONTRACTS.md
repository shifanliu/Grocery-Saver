# API Contracts

This document defines all API endpoint contracts for grocery-api, ensuring that the frontend can directly integrate and future database switching will not break the interfaces.

## Base Response Format

All API responses contain the following fields:
- `ts`: Timestamp (ISO format)
- Other fields vary depending on the endpoint

## Items API

### 1. GET /items

**Description**: List items with support for pagination, sorting, and filtering

**Query Parameters**:
- `store_id` (optional): Store ID, used to filter items by store
- `limit` (optional): Number of items to return, default 20, range 1–100
- `offset` (optional): Number of items to skip, default 0
- `sort` (optional): Sort field, valid values: `last_seen_time`, `name`, `price`, `promotion_price`, default `last_seen_time`
- `order` (optional): Sort direction, valid values: `asc`, `desc`, default `desc`

**Response Format**:
```json
{
  "items": [
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
  ],
  "limit": 20,
  "offset": 0,
  "total": 1,
  "ts": "2025-01-27T10:30:00.000Z"
}
```

### 2. GET /items/{item_id}

**Description**: Get a single item by ID

**Path Parameters**:
- `item_id`: Item ID, supports two formats:
  - Single ID: `"100364490"`
  - Store:ID format: `"costco_business_delivery:100364490"`

**Response Format**:
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

**Error Response** (404):
```json
{
  "detail": "Item not found"
}
```

### 3. GET /items/search

**Description**: Search items

**Query Parameters**:
- `q` (required): Search keyword
- `store_id` (optional): Store ID, used to filter items by store

**Response Format**:
```json
{
  "items": [
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
  ],
  "query": "honey",
  "store_id": null,
  "count": 1,
  "ts": "2025-01-27T10:30:00.000Z"
}
```

### 4. POST /items

**Description**: Create or update an item (temporary in-memory storage, for debugging)

**Request Body**:
```json
{
  "id": "test_item_001",
  "name": "Test Product",
  "store_id": "test_store",
  "price": 9.99,
  "promotion_price": 7.99,
  "category": "Test Category",
  "active": true,
  "last_seen_time": "2025-01-27T10:30:00.000Z"
}
```

**Required Fields**:
- `id`: Item ID
- `name`: Item name
- `store_id`: Store ID

**Optional Fields**:
- `price`: Price
- `promotion_price`: Promotion price
- `category`: Category
- `active`: Whether active (default: true)
- `last_seen_time`: Last update time (default: current time)

**Response Format**:
```json
{
  "success": true,
  "item": {
    "id": "test_item_001",
    "name": "Test Product",
    "price": 9.99,
    "promotion_price": 7.99,
    "store_id": "test_store",
    "last_seen_time": "2025-01-27T10:30:00.000Z",
    "category": "Test Category",
    "active": true
  },
  "ts": "2025-01-27T10:30:00.000Z"
}
```

**Error Response** (400):
```json
{
  "detail": "Missing required field: id"
}
```

### 5. POST /items/bulk_upsert

**Description**: Bulk update items (database mode)

**Request Body**:
```json
{
  "items": [
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
  ]
}
```

**Response Format**:
```json
{
  "upserted": 1
}
```

## Stores API

### 1. GET /stores

**Description**: List all stores

**Response Format**:
```json
{
  "stores": [
    {
      "id": "costco_business_delivery",
      "name": "Costco Business Delivery",
      "location": ""
    },
    {
      "id": "3132",
      "name": "Safeway",
      "location": ""
    }
  ],
  "count": 2,
  "ts": "2025-01-27T10:30:00.000Z"
}
```

### 2. GET /stores/stats

**Description**: Get repository statistics

**Response Format**:
```json
{
  "items": 3365,
  "stores": 2,
  "loaded": true,
  "store_counts": {
    "costco_business_delivery": 824,
    "3132": 2541
  },
  "ts": "2025-01-27T10:30:00.000Z"
}
```

### 3. POST /stores

**Description**: Create a store (database mode)

**Request Body**:
```json
{
  "id": "new_store",
  "name": "New Store",
  "location": "San Francisco, CA"
}
```

**Response Format**:
```json
{
  "ok": true
}
```

## Data Models

### Item Model
```json
{
  "id": "string",
  "name": "string",
  "price": "number|null",
  "promotion_price": "number|null",
  "store_id": "string",
  "last_seen_time": "string (ISO datetime)",
  "category": "string",
  "active": "boolean"
}
```

### Store Model
```json
{
  "id": "string",
  "name": "string",
  "location": "string"
}
```

## Error Handling

All APIs use standard HTTP status codes:

- `200`: Success
- `400`: Bad request
- `404`: Resource not found
- `500`: Internal server error

Error response format:
```json
{
  "detail": "Error description"
}
```

## Notes

1. **Time format**: All time fields use ISO 8601 format  
2. **Pagination**: Use `limit` and `offset` parameters for pagination  
3. **Sorting**: Supports ascending and descending sorting on multiple fields  
4. **Search**: Item name search is case-insensitive  
5. **ID format**: Item IDs support both single ID and `store:id` formats  
6. **Temporary storage**: The POST /items endpoint stores data in memory when in CSV mode; data will be lost after restart  
7. **Database mode**: When switched to database mode, all APIs maintain the same contracts  
