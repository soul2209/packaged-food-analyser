import json
import urllib.error
import urllib.request

OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=code,product_name,product_name_en,generic_name,brands,ingredients_text,ingredients_text_en,ingredients_text_hi,nutriments"
OFF_HEADERS = {"User-Agent": "PackagedFoodAnalyser/0.3 (college mini project)"}


class LookupUnavailable(Exception):
    """Open Food Facts could not be reached."""


def nutrients_from_off(nutriments):
    mapping = {
        "energy_kcal": "energy-kcal_100g",
        "fat_g": "fat_100g",
        "sat_fat_g": "saturated-fat_100g",
        "trans_fat_g": "trans-fat_100g",
        "carbs_g": "carbohydrates_100g",
        "sugars_g": "sugars_100g",
        "protein_g": "proteins_100g",
        "fibre_g": "fiber_100g",
    }
    out = {}
    for key, source in mapping.items():
        value = nutriments.get(source)
        if isinstance(value, (int, float)):
            out[key] = round(float(value), 3)
    if "energy_kcal" not in out and isinstance(nutriments.get("energy_100g"), (int, float)):
        out["energy_kcal"] = round(float(nutriments["energy_100g"]) / 4.184, 1)
    sodium = nutriments.get("sodium_100g")
    if isinstance(sodium, (int, float)):
        out["sodium_mg"] = round(float(sodium) * 1000, 1)
    elif isinstance(nutriments.get("salt_100g"), (int, float)):
        out["sodium_mg"] = round(float(nutriments["salt_100g"]) * 400, 1)
    return out


def fetch_from_off(barcode, timeout=10):
    """Return a product dict from Open Food Facts, None if it has no usable data.
    Raises LookupUnavailable if the service cannot be reached."""
    request = urllib.request.Request(OFF_URL.format(code=barcode), headers=OFF_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise LookupUnavailable(str(exc))
    except Exception as exc:
        raise LookupUnavailable(str(exc))
    if data.get("status") != 1:
        return None
    item = data.get("product") or {}
    ingredients = ""
    for key in ("ingredients_text", "ingredients_text_en", "ingredients_text_hi"):
        ingredients = (item.get(key) or "").strip()
        if ingredients:
            break
    ingredients = ingredients.replace("_", "")
    nutrients = nutrients_from_off(item.get("nutriments") or {})
    name = (item.get("product_name") or item.get("product_name_en") or item.get("generic_name") or "").strip() or "Unnamed product"
    brand = (item.get("brands") or "").split(",")[0].strip()
    return {
        "barcode": barcode,
        "name": name,
        "brand": brand,
        "ingredients_text": ingredients,
        "nutrients": nutrients,
        "source": "openfoodfacts",
    }


def _save(conn, product):
    conn.execute(
        "INSERT OR REPLACE INTO products (barcode, name, brand, ingredients_text, nutrients_json, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (product["barcode"], product["name"], product["brand"], product["ingredients_text"],
         json.dumps(product["nutrients"]), product["source"]),
    )
    conn.commit()


def valid_gtin(code):
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in code]
    check = digits.pop()
    total = 0
    for i, d in enumerate(reversed(digits)):
        total += d * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10 == check


def _candidates(barcode):
    """Same product can be scanned as UPC-A (12), EAN-13 or with leading zeros."""
    out = [barcode]
    for variant in (barcode.zfill(13), barcode.lstrip("0")):
        if variant and variant not in out and len(variant) in (8, 12, 13, 14):
            out.append(variant)
    return out


def _from_row(row):
    return {
        "barcode": row["barcode"],
        "name": row["name"],
        "brand": row["brand"],
        "ingredients_text": row["ingredients_text"] or "",
        "nutrients": json.loads(row["nutrients_json"] or "{}"),
        "source": row["source"],
    }


def lookup_barcode(conn, barcode, fetch=None):
    """Local database first, then live Open Food Facts (cached locally when usable).
    Returns (product, error, status)."""
    fetch = fetch or fetch_from_off
    candidates = _candidates(barcode)
    for code in candidates:
        row = conn.execute("SELECT * FROM products WHERE barcode = ?", (code,)).fetchone()
        if row:
            return _from_row(row), None, 200

    product = None
    try:
        for code in candidates:
            product = fetch(code)
            if product:
                break
    except LookupUnavailable:
        return None, "Could not reach Open Food Facts. Check your internet connection, or photograph the label instead.", 503
    if not product:
        return None, "This barcode is not in our database or Open Food Facts yet. Photograph the label instead.", 404
    if not product["ingredients_text"] and not product["nutrients"]:
        return None, (f"Found \"{product['name']}\" but Open Food Facts has no ingredients or nutrition data for it. "
                      "Photograph the label instead."), 422
    _save(conn, product)
    return product, None, 200


def list_products(conn, limit=20):
    rows = conn.execute("SELECT barcode, name, brand FROM products ORDER BY name LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
