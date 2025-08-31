# Repository Layer

这个仓库层提供了统一的数据访问接口，支持从CSV文件读取数据到内存，并且可以轻松切换到数据库实现。

## 设计目标

1. **统一接口**: 提供一致的方法签名，无论底层是CSV还是数据库
2. **易于切换**: 通过配置即可在CSV和数据库之间切换
3. **内存存储**: CSV数据加载到内存，提供快速查询
4. **调试友好**: 支持临时写入内存，方便调试

## 核心组件

### 1. BaseRepository (抽象基类)
定义统一的数据访问接口：
- `load_csv(paths)` - 加载CSV文件
- `list_items()` - 列出商品（支持分页、排序、过滤）
- `get_item(item_id)` - 获取单个商品（支持 `store:id` 格式）
- `search_items(q, store_id)` - 搜索商品
- `list_stores()` - 列出商店
- `upsert_item(item)` - 更新或插入商品
- `get_stats()` - 获取统计信息

### 2. CSVRepository (CSV实现)
- 从CSV文件加载数据到内存
- 提供快速的内存查询
- 支持临时写入（调试用）
- 自动推断商店名称

### 3. DatabaseRepository (数据库实现)
- 使用SQLAlchemy进行数据库操作
- 实现相同的接口
- 支持事务和持久化存储

### 4. RepositoryManager (管理器)
- 统一的访问入口
- 根据配置自动选择实现
- 处理初始化逻辑

## 使用方法

### 基本使用

```python
from app.repository.manager import repo_manager

# 初始化（会自动加载CSV数据）
repo_manager.initialize()

# 列出商品
items = repo_manager.list_items(limit=10, store_id="costco_business_delivery")

# 搜索商品
results = repo_manager.search_items("honey")

# 获取单个商品
item = repo_manager.get_item("100364490")
# 或者使用 store:id 格式
item = repo_manager.get_item("costco_business_delivery:100364490")

# 列出商店
stores = repo_manager.list_stores()

# 获取统计信息
stats = repo_manager.get_stats()
```

### 配置

通过环境变量控制仓库类型：

```bash
# 使用CSV模式（默认）
export REPO_TYPE=csv

# 使用数据库模式
export REPO_TYPE=db
```

### CSV文件路径配置

在 `config.py` 中配置CSV文件路径：

```python
CSV_PATHS = [
    Path("apps/grocery-collector/costco_items.csv"),
    Path("apps/grocery-collector/safeway_items.csv"),
]
```

## API端点

### 商品相关
- `GET /items` - 列出商品（支持分页、排序、过滤）
- `GET /items/{item_id}` - 获取单个商品
- `GET /items/search?q={query}` - 搜索商品
- `POST /items/bulk_upsert` - 批量更新商品

### 商店相关
- `GET /stores` - 列出商店
- `GET /stores/stats` - 获取统计信息

## 数据格式

### 商品数据
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

### 商店数据
```json
{
  "id": "costco_business_delivery",
  "name": "Costco Business Delivery",
  "location": ""
}
```

## 测试

运行测试脚本验证功能：

```bash
cd apps/grocery-api
python test_csv_repo.py
```

## 扩展

### 添加新的数据源

1. 继承 `BaseRepository`
2. 实现所有抽象方法
3. 在 `create_repository()` 工厂函数中添加新类型
4. 更新配置

### 添加新的查询方法

1. 在 `BaseRepository` 中添加抽象方法
2. 在所有实现类中实现该方法
3. 在 `RepositoryManager` 中添加代理方法
4. 在路由中添加对应的端点

## 性能考虑

- CSV模式：数据加载到内存，查询速度快，但内存占用较高
- 数据库模式：支持大数据量，但查询速度相对较慢
- 建议：开发调试使用CSV模式，生产环境使用数据库模式
