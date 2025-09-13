import sys, os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]   # D:/GrocerySaver/grocery
load_dotenv(ROOT / ".env")
sys.path.append(str(ROOT))

from apps.grocery_api.app.database import DATABASE_URL
print("Using DB:", DATABASE_URL)

from apps.grocery_api.app.database import SessionLocal
from apps.grocery_api.app.repository.db_repo import DatabaseRepository
from costco_fetch_new import fetch_all_categories
from safeway_fetch import fetch_all_pages


def main():
    with SessionLocal() as db:
        repo = DatabaseRepository(db)

        # Costco
        all_rows = fetch_all_categories()
        for r in all_rows:
            repo.upsert_item(r)

        # Safeway
        safeway_rows = fetch_all_pages()
        for r in safeway_rows:
            repo.upsert_item(r)

        print(f"[DONE] Costco {len(all_rows)} , Safeway {len(safeway_rows)},  loading into DB")


if __name__ == "__main__":
    main()
