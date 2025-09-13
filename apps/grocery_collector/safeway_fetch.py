import csv
import datetime as dt
import time
import requests
from urllib.parse import urlparse

STORE_ID = "3132"
ROWS = 30

PAGES = [
    {
        "referer": "https://www.safeway.com/order/fall/labor-day/meat-and-seafood.html",
        "widget_id": "GR-copyo-f2241d10",
    },
    {
        "referer": "https://www.safeway.com/order/fall/back-to-school/beverages.html",
        "widget_id": "GR-Backt-587a37a7",
    },
    {
        "referer": "https://www.safeway.com/home/chips-and-dip.html",
        "widget_id": "GR-copyo-afc045df",
    },
    {
        "referer": "https://www.safeway.com/home/frozen-treats.html",
        "widget_id": "GR-copyo-864899ad",
    },
    {
        "referer": "https://www.safeway.com/home/trending-treats.html",
        "widget_id": "GR-C-Categ-fac613eb",
    },
]

BASE_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en',
    'ocp-apim-subscription-key': 'e914eec9448c4d5eb672debf5011cf8f',
    'priority': 'u=1, i',
    'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
}

def first(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)) and v != "":
            return v
        if isinstance(v, list) and v:
            return v[0]
    return None

def parse_category_from_referer(referer: str) -> str:
    seg = urlparse(referer).path.rstrip('/').split('/')[-1]
    return seg[:-5] if seg.endswith('.html') else seg

def normalize_item(doc, last_seen_iso, category_override=None):
    iid = first(doc.get("productId"), doc.get("sku"), doc.get("upc"),
                doc.get("id"), doc.get("uniqueId"))
    name = first(doc.get("name"), doc.get("title"), doc.get("productName"))
    price = first(
        doc.get("price"),
        doc.get("priceValue"),
        doc.get("storePrice"),
        (doc.get("pricing") or {}).get("price") if isinstance(doc.get("pricing"), dict) else None,
        (doc.get("prices") or {}).get("list") if isinstance(doc.get("prices"), dict) else None,
    )
    promo_price = first(
        doc.get("promoPrice"),
        doc.get("salePrice"),
        (doc.get("pricing") or {}).get("promoPrice") if isinstance(doc.get("pricing"), dict) else None,
        (doc.get("prices") or {}).get("sale") if isinstance(doc.get("prices"), dict) else None,
    )
    category = category_override if category_override else first(
        doc.get("category"),
        doc.get("categoryName"),
        doc.get("department"),
        doc.get("aisle"),
        (doc.get("categories") or []),
        (doc.get("allCategories") or []),
    )
    active = bool(first(doc.get("active"), doc.get("isActive"), True))

    return {
        "id": iid,
        "name": name,
        "price": price,
        "promotion_price": promo_price,
        "store_id": STORE_ID,
        "last_seen_time": last_seen_iso,
        "category": category,
        "active": active,
    }

def build_url(start: int, widget_id: str) -> str:
    return (
        "https://www.safeway.com/abs/pub/xapi/wcax/pathway/search"
        f"?request-id=8831755831883553807"
        f"&url=https://www.safeway.com"
        f"&search-uid=&q=&rows={ROWS}&start={start}"
        f"&channel=instore&storeid={STORE_ID}&sort="
        f"&widget-id={widget_id}"
        f"&visitorId=83ba34e7-fb06-41e8-9416-e000148fdc96"
        f"&uuid=null&pgm=abs&includeOffer=true&banner=safeway"
        f"&dvid=web-4.1search"
    )

def fetch_all_items_for_page(referer: str, widget_id: str):
    headers = dict(BASE_HEADERS)
    headers["referer"] = referer

    start = 0
    total_number = None
    rows = []
    last_seen_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    cat = parse_category_from_referer(referer)

    while (total_number is None) or (len(rows) < total_number):
        url = build_url(start=start, widget_id=widget_id)
        try:
            resp = requests.get(url, headers=headers, timeout=20)
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
        time.sleep(0.3)

    return rows

def fetch_all_pages():
    all_rows = []
    for p in PAGES:
        part = fetch_all_items_for_page(
            referer=p["referer"],
            widget_id=p["widget_id"],
        )
        all_rows.extend(part)
    return all_rows

def write_csv(rows, out_path="safeway_items.csv"):
    fieldnames = ["id", "name", "price", "promotion_price", "store_id", "last_seen_time", "category", "active"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return out_path

if __name__ == "__main__":
    rows = fetch_all_pages()
    path = write_csv(rows, "safeway_items.csv")
    print(f"[DONE] 已写入 {len(rows)} 行到 {path}")
