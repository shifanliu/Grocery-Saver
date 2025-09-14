# -*- coding: utf-8 -*-
import csv
import datetime as dt
import time
import requests
from urllib.parse import urlparse

STORE_ID = "COSTCO_95616"
ROWS = 96 

BASE_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://www.costcobusinessdelivery.com",
    "referer": "https://www.costcobusinessdelivery.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "x-api-key": "63b948d8-7d06-451b-acbe-f75815e96252", 
}

CATEGORIES = [
    "https://www.costcobusinessdelivery.com/baking.html",
    "https://www.costcobusinessdelivery.com/breads-bakery.html",
    "https://www.costcobusinessdelivery.com/cereal-breakfast.html",
    "https://www.costcobusinessdelivery.com/dairy-eggs.html",
    "https://www.costcobusinessdelivery.com/deli.html",
    "https://www.costcobusinessdelivery.com/fresh-produce.html",
    "https://www.costcobusinessdelivery.com/frozen-foods.html",
    "https://www.costcobusinessdelivery.com/health-beauty.html",
    "https://www.costcobusinessdelivery.com/meat-seafood.html",
    "https://www.costcobusinessdelivery.com/pantry-dry-goods.html",
    "https://www.costcobusinessdelivery.com/pet-supplies.html",
]

def parse_category_from_url(url: str) -> str:
    seg = urlparse(url).path.rstrip("/").split("/")[-1]
    return seg[:-5] if seg.endswith(".html") else seg

def normalize_item(doc, last_seen_iso, category_override=None):
    iid = (
        doc.get("item_number")
        or doc.get("id")
        or doc.get("group_id")
    )
    name = (
        doc.get("item_product_name")
        or doc.get("item_name")
        or doc.get("name")
    )

    price = doc.get("item_location_pricing_listPrice")
    promo_price = doc.get("item_location_pricing_salePrice")

    if not price:
        price = doc.get("minSalePrice") or doc.get("maxSalePrice")
    if not promo_price:
        promo_price = price

    return {
        "id": iid,
        "name": name,
        "price": price,
        "promotion_price": promo_price,
        "store_id": STORE_ID,
        "last_seen_time": last_seen_iso,
        "category": category_override,
        "active": True,
    }


def build_url(category_url: str, start: int) -> str:
    return (
        "https://search.costcobusinessdelivery.com/api/apps/www_costcobusinessdelivery_com/"
        "query/www_costcobusinessdelivery_com_navigation"
        f"?expoption=lucidworks&q=*%3A*&locale=en-US&start={start}"
        f"&expand=false&userLocation=CA&loc=893&rows={ROWS}"
        f"&url={urlparse(category_url).path}&chdheader=true"
    )

def fetch_all_items_for_category(category_url: str):
    headers = dict(BASE_HEADERS)
    start = 0
    total_number = None
    rows = []
    last_seen_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    cat = parse_category_from_url(category_url)

    while (total_number is None) or (len(rows) < total_number):
        url = build_url(category_url, start=start)
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[WARN] {cat} 请求失败：{e}")
            break

        data = resp.json()
        if total_number is None:
            total_number = (data.get("response") or {}).get("numFound") or 0

        docs = (data.get("response") or {}).get("docs") or []
        if not docs:
            print(f"[INFO] {cat} 本页无 docs，提前结束。")
            break

        for d in docs:
            row = normalize_item(d, last_seen_iso, category_override=cat)
            if row["id"] and row["name"]:
                rows.append(row)

        print(f"[PAGE] [{cat}] start={start} 获取 {len(docs)} 条；累计 {len(rows)}/{total_number}")
        start += ROWS
        time.sleep(0.5)

    return rows

def fetch_all_categories():
    all_rows = []
    for url in CATEGORIES:
        part = fetch_all_items_for_category(url)
        all_rows.extend(part)
    return all_rows

def write_csv(rows, out_path="costco_items.csv"):
    fieldnames = ["id", "name", "price", "promotion_price", "store_id", "last_seen_time", "category", "active"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return out_path

if __name__ == "__main__":
    rows = fetch_all_categories()
    path = write_csv(rows)
    print(f"[DONE] 已写入 {len(rows)} 行到 {path}")
