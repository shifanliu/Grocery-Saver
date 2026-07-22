"""
Database module for initializing SQLAlchemy engine, session, and base model.

This module configures the database connection using SQLAlchemy, including:
- The default SQLite database URL (or DATABASE_URL from environment).
- Engine creation with appropriate connection arguments.
- Session factory for database transactions.
- Base class for declarative models.
- Dependency-injected `get_db` generator for FastAPI routes.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# apps/grocery_api/app/database.py -> repo root is 3 levels up
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "grocery.db"
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """
    Provide a database session for request handling.

    Yields:
        Session: SQLAlchemy session object.
    Ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
