import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# CSV 
DATA_CSV_FILES = [
    ROOT / "grocery-collector" / "costco_items.csv",
    ROOT / "grocery-collector" / "safeway_items.csv",
]

DEFAULT_LIMIT = 20

# database url
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://grocery:grocery@localhost:5432/grocery",
)
