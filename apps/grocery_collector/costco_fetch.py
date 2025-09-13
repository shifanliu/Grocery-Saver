# -*- coding: utf-8 -*-
import os
import re
import csv
import time
import datetime as dt
import requests
from lxml import html
from urllib.parse import urljoin, urlparse

BASE = "https://www.costcobusinessdelivery.com"
STORE_ID = "costco_business_delivery"
OUT_CSV = "costco_items.csv"
QPS = 0.6                       

COSTCO_COOKIE = (
    "kndctr_97B21CFE5329614E0A490D45_AdobeOrg_cluster=or2; "
    "kndctr_97B21CFE5329614E0A490D45_AdobeOrg_identity=CiY0ODQyMzQ0Njg0MTEzNTExOTM5Mjc2MTA0NzI2Nzg4MDcxNzY5M1IQCJPk2puOMxgBKgNPUjIwAfABk-Tam44z; "
    "AMCV_97B21CFE5329614E0A490D45%40AdobeOrg=MCMID|48423446841135119392761047267880717693; "
    "selectedLanguage=-1; "
    "ak_bmsc=34DD8669FAB7DE6866A242672BF8C392~000000000000000000000000000000~YAAQbKfLFwx78riYAQAALrl24xyyT0ufdgQFtwAiAkwhH+9oRb/3IrhsdIRoYfpJNSp2eDbwlEwiCNlCYwOQWkdzHxkx/VE4AQdI88BS29bpr6N0ylOBwbRfiTl9Htsb5gC60JCwcXxSv/07U86VPyE5o6LAyPTSCgz+YTkSUXi/usgF3DkilDYi+zYlmKMaQyLl6m1S1YQyBhHwk32XYax7raCiiJySbL+1PteIfCchffPKeBFTTELXA+PgEymp3z8fe3X/YCxeg4aMHnb+PAoh9avNH4UKy1Ff2U/AQkId+t302ShXf46eBLMpdX50Lo88cvk5nTU70ugl2A+eyAwF78Swjc/9zagyDND9F7cwDCy6j+G60EDeutDIoAksEznzyr+yZu6dM2/yxkR6PA3OsOv8Pk5ULZKMMph8M7dLO7aaRcAAABakibUwTIg9fLAFeT07vgWxafO8d8LFl0ffJAKZiCQoSOkFP3Y=; "
    "CriteoSessionUserId=8e5c3a14-1583-418d-922e-3ecf4cc492ca; "
    "mboxEdgeCluster=35; "
    "WC_BD_ZIP=95616; WC_BD_WHS=893; C_LOC=USCA; WC_BD_LOC=Davis%7CCA%7CUS; "
    "_abck=BF8536821D736850C19307EFA68F8A40~0~YAAQbKfLF2eE8riYAQAAbdt24w6QwtXdg+DAmXQ+Y18YPqzzgpKNTG5CG5wjcw/RO4yejgdjEUPGTYzDrdeAZljSE/1HGF80z+enkYFJAinRjjRBG3i0e01fbKucijctiXaES5OMna4w/DYihmr0DQw4+hAGm7XyBHlpewgPHMHhKJQMoQqegs0lIVw0FsGT8ksXg8EZQzdVKZ6Gwn9cxPjtdRdDL59Tj+doHBwvFjGWWUsQgLIPVa2KhvQ+AqQuwT74ZRqeCfh+4djgt7b2bcYp1+zSmx/WsCBxTk2s4jFWGtUTvQtG7+xpqVUATRFPMAayBc79wQnS+/G2K89aDo+Twj2Wr1o4EeK0ogO8VrNosaTu0/nJdmTKId9L5Anh8nCL0ikUbdH70NzuF3Q9AeF+TutJzIW8xBIC/qQ5eFPUYjBI7+xKAkcY2DntkQXoprS22vWm+pEu0Jv60dDfiHvLiUEut75UNnI9OBNfoWZTwhtGyZFThzqONV7+tBsKhhUPTPAmm20Uja0xKAQYf8Gvf1Ym62yTumbbrushp5XLjBeqy//9LD5zVDzfPvIs1YNJulqFFqIOK0QQmXbzNfqOCsF2KoNg92Qog7oel2qDXIixTIRIdwNGbNJWkESj/FDuUe9w6Hyw92+o55zMVXw=~-1~-1~1756166464~~; "
    "BDO=pm2; akaas_AC_USBD=2147483647~rv=92~id=5006e32aa5bbc5e93ac949cb2376d791; WC_SESSION_ESTABLISHED=true; WC_ACTIVEPOINTER=-1%2C11301; "
    "bm_so=F01143DCA914E0A0A729861CFF2B3105E65A6EEDF1696CE90E5AB04FE669C514~YAAQZafLF8vXHLqYAQAAWz6Y4wR5IQLUMj42aQbHGSnl5cOVnBS/ZJqUgIh6hM4Q+deIQMKwKKUJBIbtEXOVciVuKqp6uuBoJcmz4RCHkGGiYJgfqO7UGbjzi/4LYgw2gGxKjoaJ9B5gMgvuNzfjogJIF0rc4xjVqzIuUWY1HZX4AemKZOZNqiYNowhhVvzbshuN2CO3LjV1kLyjl79nv96lPRcnLTtdZaXbDpPJuKEVJ+S8fW7N2+1JgzzuyIf8KyAx3K9Mn7pxdJzxj7e8llkk6N/b2UdMwESPJtgOtVBNnQ4xvm0JOIptfW00XIiJXdZy6swC05mfdxKs3pg0xdgYQxPBsIp4Zxr8n51pB5a0NiM7nCKeesLteYTZP9vMK7DGKRykLUQeoI9AEsucWBmPRtNkS89T0xzKONaluTpRYw/Ua9Cgcb9lzl7AODxwVbK90K0h4eRvfbSHp7/1LEwqP8vn/D4GC9E+mOo=; "
    "bm_sz=5B0CC923E6BDB20B0D98FDB41782798F~YAAQZafLF83XHLqYAQAAWz6Y4xxOwVQvUaeomfLLhahGtTDikFlZ+4faX3bNlSnLdGuBxvw7P2NPh2ijT1JNCArcEOVs055xTgJsZk9to5xj1ZQmCPS1E4rHiHqggwjeDqtpglxOVFcE5sr/ZlQwwtI/4VfN64ETgO0hVWLrmiVqBuS51iCiih0v/vwpZ+PBdR3JvCBHYFW2rOa6HfAkEW3KWTNVdAOKORRiSMyIlpi3WwSPbMSe6IPRQ6XdEzOd/CGXAMMeDZcfRVDrqMvqhLZZiqFL5ucqkE1VAGOPm19eAfgRPqT2faqcFV9YZsUhLa89TaoL52cwX9s7eHXB4E3WYwwW5VHpBp3AACGATZ+sTv8qV3A6RIMWc/T+gUsjqPO0WNo5pldFYkwWGM5rJjnQKOwwBo6pXjrppqGfqoblrqJ50Dw2bJAMRcMIcU5FghXMp16yDCoFqizZB0kjF/UQFfR4KIDBViSFLUTcBha8fL4Wd7ZFTNQBu3eIcQ==~3425081~4604739; "
    "bm_sv=3B33611A4860CCB45363A7D9DFA5B33D~YAAQaafLFz/Sd+GYAQAANkKY4xzUwG4MO1sl+L+pghbAMv7mp3u2qwbYQMPriIeTaZr52A9LGkvdM48X0y/ChxrB1fERpgXas/ZVEpe53iduSOrRkovP5XbOGgWyaaci4ku5Vy4Q1RnS4LX40Wl5H2o9c6KpmjVnvUoQYKNTACkcfgkM5hc8BdOfwrI03zlyW6LOJPzS3BngaMqkSLBNuCtByoPKsjl0mCN5AwwafKgdnFchLNILkPdwruYzOhEEQBwhdpSUFmTwDbfHvuEnATY=~1; "
    "OptanonConsent=isGpcEnabled=0&datestamp=Mon+Aug+25+2025+16%3A37%3A46+GMT-0700+(Pacific+Daylight+Time)&version=202401.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=b85e54a1-45d3-4c66-8179-e28f791b3b16&interactionCount=1&landingPath=NotLandingPage&groups=BG117%3A1%2CC0001%3A1%2CC0003%3A1%2CC0002%3A1%2CSPD_BG%3A1%2CC0004%3A1&AwaitingReconsent=false; "
    "mbox=session#48423446841135119392761047267880717693-sAZqVN#1756166923; "
    "cto_bundle=46E3Ll9mVlAwZkdIaEdDT0lLMnd5UFFsOHJuUzVxdjBpQUpFVjJlT0p3SUR5Uk5SWFVEVnhHeUZKJTJGMDFqSUh4dyUyQklUNExGZlNocjl1eDR4U1I3SlY2ciUyQkV5VU5rQnVZJTJGUTNHRjBBNHZnTHVFYXJ6JTJCcWxiZzVTSDRqUXFIRkJZUFFtMDQyV2ZFUU1ZN3NDTzB0QTVHakZCZDE2MlpudEI4aTExMGIxMURaRlVtS0dvJTNE; "
    "bm_lso=F01143DCA914E0A0A729861CFF2B3105E65A6EEDF1696CE90E5AB04FE669C514~YAAQZafLF8vXHLqYAQAAWz6Y4wR5IQLUMj42aQbHGSnl5cOVnBS/ZJqUgIh6hM4Q+deIQMKwKKUJBIbtEXOVciVuKqp6uuBoJcmz4RCHkGGiYJgfqO7UGbjzi/4LYgw2gGxKjoaJ9B5gMgvuNzfjogJIF0rc4xjVqzIuUWY1HZX4AemKZOZNqiYNowhhVvzbshuN2CO3LjV1kLyjl79nv96lPRcnLTtdZaXbDpPJuKEVJ+S8fW7N2+1JgzzuyIf8KyAx3K9Mn7pxdJzxj7e8llkk6N/b2UdMwESPJtgOtVBNnQ4xvm0JOIptfW00XIiJXdZy6swC05mfdxKs3pg0xdgYQxPBsIp4Zxr8n51pB5a0NiM7nCKeesLteYTZP9vMK7DGKRykLUQeoI9AEsucWBmPRtNkS89T0xzKONaluTpRYw/Ua9Cgcb9lzl7AODxwVbK90K0h4eRvfbSHp7/1LEwqP8vn/D4GC9E+mOo=^1756165066918; "
    'RT="z=1&dm=costcobusinessdelivery.com&si=02e0ff98-2c4c-444c-a970-4a13771e4c9d&ss=merq0yqd&sl=g&tt=1ovk&bcn=%2F%2F17de4c0e.akstat.io%2F&obo=3&ld=1b6xh&hd=1bku1"; '
    "_lr_hb_-costco%2Fproduction-vrwno={%22heartbeat%22:1756165249733}; "
    "_lr_tabs_-costco%2Fproduction-vrwno={%22recordingID%22:%226-0198e388-4232-765b-b417-133b86fd64b9%22%2C%22sessionID%22:0%2C%22lastActivity%22:1756165309831%2C%22hasActivity%22:true%2C%22confirmed%22:false%2C%22recordingConditionThreshold%22:%2217.74652812685393%22%2C%22clearsIdentifiedUser%22:false}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Referer": BASE + "/",
    "Origin": BASE,
    # "Cookie": COSTCO_COOKIE,
}

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

def _get_tree(sess: requests.Session, url: str) -> html.HtmlElement:
    r = sess.get(url, timeout=30)
    r.raise_for_status()
    return html.fromstring(r.content)

def _text_or_none(nodes):
    if not nodes:
        return None
    n = nodes[0]
    return (n if isinstance(n, str) else n.text_content()).strip() or None

def _num(raw: str | None):
    if not raw:
        return None
    keep = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    try:
        return float(keep) if keep else None
    except ValueError:
        return None

SCRIPT_PRICE_RE = re.compile(r'(?:"|\b)price"\s*:\s*"?(\d+(?:\.\d+)?)"?', re.I)

def _extract_price_from_card(card) -> tuple[float | None, float | None]:
    attr_price = _text_or_none(card.xpath(
        ".//*[@itemprop='price']/@content | "
        ".//*[@data-price]/@data-price | "
        ".//*[contains(@class,'price') and @content]/@content | "
        ".//*[@aria-label[contains(., '$')]]/@aria-label"
    ))
    txt_price = _text_or_none(card.xpath(
        ".//*[contains(@class,'your-price') or contains(@class,'product-price') or "
        "contains(@class,'price') or contains(text(),'$')]/text()"
    ))
    attr_promo = _text_or_none(card.xpath(
        ".//*[contains(@class,'promotion-price') or contains(@class,'final-price')]/@content | "
        ".//*[contains(@class,'promotion-price') or contains(@class,'final-price')]/@data-price"
    ))
    txt_promo = _text_or_none(card.xpath(
        ".//*[contains(@class,'promotion-price') or contains(@class,'final-price') or contains(text(),'$')]/text()"
    ))
    price = _num(attr_price) or _num(txt_price)
    promo = _num(attr_promo) or _num(txt_promo)

    if price is None and promo is None:
        frag = html.tostring(card, encoding="unicode", with_tail=False)
        vals = [float(m.group(1)) for m in SCRIPT_PRICE_RE.finditer(frag)]
        if vals:
            if len(vals) == 1:
                price = vals[0]
            else:
                price, promo = max(vals), min(vals)
    return price, promo

ID_PATTERNS = [
    re.compile(r"/product\.([0-9A-Za-z\-]+)\.html", re.I),
    re.compile(r"/([^/]+)\.product\.([0-9A-Za-z\-]+)\.html", re.I),
    re.compile(r"/([0-9A-Za-z\-]+)\.html$", re.I),
]

def _id_from_url(u: str | None) -> str | None:
    if not u:
        return None
    try:
        path = urlparse(u).path
    except Exception:
        return None
    for pat in ID_PATTERNS:
        m = pat.search(path)
        if m:
            return m.groups()[-1]
    return None

def parse_product_card(card, category_name: str, seen_time_iso: str) -> dict | None:
    name = _text_or_none(card.xpath(
        ".//*[contains(@class,'product-name') or contains(@class,'product-title') "
        " or contains(@class,'description') or self::a[contains(@class,'caption')]]/text()"
    )) or _text_or_none(card.xpath(".//img/@alt"))

    link = _text_or_none(card.xpath(".//a[@href][1]/@href"))
    link = urljoin(BASE, link) if link else None

    price, promo = _extract_price_from_card(card)

    pid = _text_or_none(card.xpath(".//@data-sku | .//@data-itemid | .//@data-productid")) or _id_from_url(link)
    if not pid or not name:
        return None

    return {
        "id": pid,
        "name": name,
        "price": price,
        "promotion_price": promo,
        "store_id": STORE_ID,
        "last_seen_time": seen_time_iso,
        "category": category_name,
        "active": True,
    }

def crawl_category_to_rows(category_url: str, max_pages: int = 3, qps: float = QPS) -> list[dict]:
    sess = _session()
    rows: list[dict] = []
    url = category_url
    pages = 0
    seen_time_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    sess.headers["Referer"] = BASE + "/"

    while url and (max_pages is None or pages < max_pages):
        r = sess.get(url, timeout=30)
        r.raise_for_status()
        tree = html.fromstring(r.content)
        pages += 1

        category_name = (
            _text_or_none(tree.xpath("//h1/text() | //*[@class='category-title']/text()"))
            or urlparse(url).path.rstrip("/").split("/")[-1].removesuffix(".html")
            or "Unknown"
        )

        cards = tree.xpath(
            "//*[contains(@class,'product-tile') "
            " or (contains(@class,'product') and contains(@class,'tile')) "
            " or self::li[contains(@class,'product')]]"
        )

        for c in cards:
            try:
                row = parse_product_card(c, category_name, seen_time_iso)
                if row:
                    rows.append(row)
            except Exception:
                pass

        print(f"[page {pages}] {url} -> {len(cards)} items")

        next_href = _text_or_none(tree.xpath("//a[@rel='next' or contains(@class,'next') or @aria-label='Next']/@href"))
        url = urljoin(BASE, next_href) if next_href else None
        time.sleep(1.0 / max(qps, 0.1))

    return rows

def write_csv(rows: list[dict], out_path: str = OUT_CSV):
    fieldnames = ["id", "name", "price", "promotion_price", "store_id", "last_seen_time", "category", "active"]
    write_header = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    return out_path

def all_costco_categories():
    cats = [
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
    return cats

if __name__ == "__main__":
    categories = all_costco_categories()
    all_rows = []
    for url in categories:
        all_rows.extend(crawl_category_to_rows(url, max_pages=5, qps=0.5))
    out_path = write_csv(all_rows, OUT_CSV)
    print(f"[DONE] Costco 写入 {len(all_rows)} 行到 {out_path}")
