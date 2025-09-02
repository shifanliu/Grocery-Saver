import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 如果没有设置环境变量，就用 SQLite 本地文件
DEFAULT_DB_URL = "sqlite:///./grocery.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# SQLite 需要这个参数；Postgres 不需要
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
