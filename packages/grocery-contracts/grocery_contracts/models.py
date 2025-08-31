from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class Item(BaseModel):
    id: str
    name: str
    price: Optional[float] = None
    promotion_price: Optional[float] = None
    store_id: str
    last_seen_time: datetime
    category: Optional[str] = ""
    active: bool = True
    external_id: str

class Store(BaseModel):
    id: str
    name: str
    location: str = ""
