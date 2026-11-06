import argparse
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.products import nutrients_from_off, valid_gtin

URL = "https://world.openfoodfacts.org/api/v2/search"
FIELDS = "code,product_name,brands,ingredients_text,nutriments"
HEADERS = {"User-Agent": "PackagedFoodAnalyser/0.2 (college mini project; one-off import)"}
REQUIRED = ("sugars_g", "sodium_mg", "sat_fat_g", "energy_kcal")


def usable(item):
    code = (item.get("code") or "").strip()
    name = (item.get("product_name") or "").strip()
    ingredients = (item.get("ingredients_text") or "").strip()
    if not (valid_gtin(code) and name and len(ingredients) > 10):
        return None
    nutrients = nutrients_from_off(item.get("nutriments") or {})
    if any(key not in nutrients for key in REQUIRED):
        return None
    return code, name, (item.get("brands") or "").split(",")[0].strip(), ingredients, nutrients


def fetch_page(country, page, size):
    query = urllib.parse.urlencode({
        "countries_tags_en": country,
        "fields": FIELDS,
        "page_size": size,
        "page": page,
        "sort_by": "unique_scans_n",
    })
    request = urllib.request.Request(URL + "?" + query, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("products", [])


def main():
    parser = argparse.ArgumentParser(description="One-off import of Indian products from Open Food Facts into the local products table.")
    parser.add_argument("--target", type=int, default=300, help="how many usable products to keep")
    parser.add_argument("--country", default="india")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--keep-demo", action="store_true", help="keep the seeded demo products")
    args = parser.parse_args()

    db = Path(__file__).parent / "instance" / "analyser.sqlite"
    conn = sqlite3.connect(db)
    if not args.keep_demo:
        conn.execute("DELETE FROM products WHERE source = 'demo'")

    saved = 0
    for page in range(1, args.max_pages + 1):
        try:
            items = fetch_page(args.country, page, 100)
        except Exception as exc:
            print(f"Page {page} failed: {exc}")
            break
        if not items:
            break
        for item in items:
            row = usable(item)
            if not row:
                continue
            code, name, brand, ingredients, nutrients = row
            conn.execute(
                "INSERT OR REPLACE INTO products (barcode, name, brand, ingredients_text, nutrients_json, source) "
                "VALUES (?, ?, ?, ?, ?, 'openfoodfacts-snapshot')",
                (code, name, brand, ingredients, json.dumps(nutrients)),
            )
            saved += 1
        conn.commit()
        print(f"Page {page}: {saved} products saved so far")
        if saved >= args.target:
            break
        time.sleep(7)

    conn.commit()
    conn.close()
    print(f"Done. {saved} products stored. The app now reads them from the local database only.")


if __name__ == "__main__":
    main()
