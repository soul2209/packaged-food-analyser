import json
import sqlite3
import sys
from pathlib import Path

from app.products import valid_gtin

FIELDS = ("energy_kcal", "fat_g", "sat_fat_g", "trans_fat_g", "carbs_g", "sugars_g", "protein_g", "fibre_g", "sodium_mg")

if len(sys.argv) < 5:
    print("Usage: python add_product.py BARCODE NAME BRAND 'INGREDIENTS' key=value ...")
    print("Keys: " + ", ".join(FIELDS) + " (all per 100 g)")
    sys.exit(1)

barcode, name, brand, ingredients = sys.argv[1:5]
if not valid_gtin(barcode):
    sys.exit("Invalid barcode check digit.")
nutrients = {}
for pair in sys.argv[5:]:
    key, _, value = pair.partition("=")
    if key not in FIELDS:
        sys.exit(f"Unknown nutrient key: {key}")
    nutrients[key] = float(value)

db = Path(__file__).parent / "instance" / "analyser.sqlite"
conn = sqlite3.connect(db)
conn.execute(
    "INSERT OR REPLACE INTO products (barcode, name, brand, ingredients_text, nutrients_json, source) VALUES (?, ?, ?, ?, ?, 'label')",
    (barcode, name, brand, ingredients, json.dumps(nutrients)),
)
conn.commit()
print(f"Saved {name} ({barcode})")
