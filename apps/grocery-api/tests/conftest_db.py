# tests/conftest_db.py
import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ① 测试用 Engine（session 级别，共享一套内存库）
@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("data") / "test.db"
    url = f"sqlite:///{db_file}"
    return create_engine(url, connect_args={"check_same_thread": False})

# ② 把 app.database 绑定到测试 Engine（路由无论从哪拿 Session，都用同一库）
@pytest.fixture(scope="session", autouse=True)
def bind_app_database_to_test_engine(engine):
    import app.database as dbmod
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    dbmod.engine = engine
    dbmod.SessionLocal = TestSessionLocal
    dbmod.Base.metadata.create_all(bind=engine)
    yield

# ③ Session 工厂 + 每用例一个 Session
@pytest.fixture(scope="session")
def SessionLocal(engine):
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db_session(SessionLocal):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# ④ 强制仓库用 DB，并在每个用例前后重置 repo_manager（全局单例）
@pytest.fixture(autouse=True)
def force_db_and_reset_repo_manager():
    from app.repository.config import RepositoryConfig
    from app.repository.manager import repo_manager
    RepositoryConfig.REPO_TYPE = "db"
    repo_manager._initialized = False
    repo_manager._repo = None
    yield
    repo_manager._initialized = False
    repo_manager._repo = None

# ⑤ 每用例清空表，避免重复主键/计数污染
@pytest.fixture(autouse=True)
def db_clean(db_session):
    from app.models import Item as DBItem, Store as DBStore
    db_session.query(DBItem).delete()
    db_session.query(DBStore).delete()
    db_session.commit()
    yield

# ⑥ 种子数据（统一 naive UTC，避免 tz 混排）
@pytest.fixture()
def seed_data(db_session):
    from app.models import Store as DBStore, Item as DBItem
    store = DBStore(id="test_store", name="Test Store", location="Davis, CA")
    db_session.add(store)

    now = datetime.utcnow()
    i1 = DBItem(
        id="item_1",
        name="Apple Juice",
        price=3.50,
        promotion_price=2.99,
        store_id="test_store",
        last_seen_time=now - timedelta(minutes=5),
        category="Beverages",
        active=True,
    )
    i2 = DBItem(
        id="item_2",
        name="Banana",
        price=0.49,
        promotion_price=None,
        store_id="test_store",
        last_seen_time=now - timedelta(minutes=3),
        category="Fruits",
        active=True,
    )
    db_session.add_all([i1, i2])
    db_session.commit()
    return {"store": store, "items": [i1, i2]}

# ⑦ FastAPI 应用 + 依赖覆盖（不再主动 initialize repo；让路由在请求里做）
@pytest.fixture()
def fastapi_app(db_session):
    from app.routers.items import router as items_router
    from app.routers.stores import router as stores_router
    from app.database import get_db, Base
    from app.repository.manager import repo_manager

    # 确保当前 session 绑定的连接也具备完整表
    Base.metadata.create_all(bind=db_session.get_bind())

    app = FastAPI()
    app.include_router(items_router, prefix="/items", tags=["items"])
    app.include_router(stores_router, prefix="/stores", tags=["stores"])

    # 覆盖 get_db 依赖
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db

    # 关键：用“当前 db_session”显式初始化仓库
    from app.repository.config import RepositoryConfig
    RepositoryConfig.REPO_TYPE = "db"
    # 清一次单例旧状态再初始化
    repo_manager._initialized = False
    repo_manager._repo = None
    repo_manager.initialize(db_session)

    return app

@pytest.fixture()
def client(fastapi_app):
    return TestClient(fastapi_app)
