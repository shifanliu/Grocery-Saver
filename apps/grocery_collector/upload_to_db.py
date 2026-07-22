import sys, os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]   # D:/GrocerySaver/grocery
load_dotenv(ROOT / ".env")
# app.* modules use bare "app.foo" imports internally (same convention as
# tests/uvicorn), so grocery_api must be on sys.path, not just the repo root.
sys.path.append(str(ROOT / "apps" / "grocery_api"))

from app.database import Base, DATABASE_URL, SessionLocal, engine
from app.repository.db_repo import DatabaseRepository
from app.models import Store as DBStore

print("Using DB:", DATABASE_URL)
Base.metadata.create_all(bind=engine)

from costco_fetch_new import fetch_all_categories
from safeway_fetch import fetch_all_pages


def ensure_store(db, store_id: str, store_name: str = None):
    store = db.get(DBStore, store_id)
    if not store:
        store = DBStore(id=store_id, name=store_name or store_id, location="")
        db.add(store)
        db.commit()
    return store


def load_rows(db, repo, rows, store_name: str):
    for r in rows:
        ensure_store(db, r["store_id"], store_name)
        repo.upsert_item(r)
    return len(rows)


def main():
    with SessionLocal() as db:
        repo = DatabaseRepository(db)
        summary = {}

        try:
            costco_rows = fetch_all_categories()
            summary["costco"] = load_rows(
                db, repo, costco_rows, "Costco Business Delivery"
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[ERROR] Costco fetch/load failed: {e}")
            summary["costco"] = 0

        try:
            safeway_rows = fetch_all_pages()
            summary["safeway"] = load_rows(db, repo, safeway_rows, "Safeway")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[ERROR] Safeway fetch/load failed: {e}")
            summary["safeway"] = 0

        print(
            f"[DONE] {datetime.utcnow().isoformat()} "
            f"Costco {summary['costco']} items, "
            f"Safeway {summary['safeway']} items loaded into DB"
        )

        if summary["costco"] == 0 and summary["safeway"] == 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
