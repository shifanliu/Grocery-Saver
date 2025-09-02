from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String, default="")


class Item(Base):
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    promotion_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    store_id: Mapped[str] = mapped_column(String, index=True)
    last_seen_time: Mapped[datetime] = mapped_column(
        DateTime, index=True, default=datetime.utcnow
    )
    category: Mapped[str] = mapped_column(String, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # external_id: Mapped[str] = mapped_column(String, index=True)
