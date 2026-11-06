# Packaged Food Analyser

Flask + Tesseract OCR + SQLite. Scans a food label (or looks up a barcode in the local database) and returns a rule-based health score, additive and allergen flags, and plain-language insights compared with WHO benchmarks.

## Setup

```
pip install -r requirements.txt
python init_db.py
python run.py
```

Install Tesseract first. Windows: the UB Mannheim installer, then add its folder to PATH. Linux: `sudo apt install tesseract-ocr`.

Open http://127.0.0.1:5000

## Pages

| Route | What it does |
|---|---|
| / | Analyse by barcode number or label photo (text editing is behind "Edit the text") |
| /history | Past scans, delete, pick two to compare |
| /compare?a=1&b=2 | Side-by-side comparison |
| /report/<id> | Printable report (Print > Save as PDF) |

## API

| Method | Route | Purpose |
|---|---|---|
| GET | /api/health | Liveness check |
| GET | /api/reference | WHO benchmark table |
| POST | /api/analyze/text | JSON `{"text": "..."}` |
| POST | /api/analyze/image | Multipart `image`, optional `barcode` |
| POST | /api/analyze/barcode-image | Multipart `image` of a barcode; decoded, then looked up |
| GET | /api/analyze/barcode/<code> | Local products table first, then live Open Food Facts (result is cached locally) |
| GET | /api/products | Products available for barcode lookup |
| GET | /api/scans | Last 50 scans |
| GET | /api/scans/<id> | One full scan |
| DELETE | /api/scans/<id> | Remove a scan |

## Layout

- `sql/schema.sql`, `sql/seed.sql`: tables and WHO, additive, allergen data
- `app/ocr.py`: image cleanup and Tesseract
- `app/parser.py`: ingredients, E-numbers, allergen statements, nutrition table
- `app/products.py`: barcode validation and local product lookup
- `import_off.py`: one-off bulk import of Indian products from an Open Food Facts snapshot (run once, then the app is offline)
- `add_product.py`: add a product from a photographed label
- `app/analysis.py`: scoring and insights
- `app/routes.py`: JSON API and page routes
- `app/templates`, `app/static`: frontend
- `tests/`: `python -m pytest`

## Scoring

Starts at 100. Sugars, sodium, saturated fat and trans fat lose points in proportion to their share of the WHO daily limit per 100 g (per 100 ml for drinks, where sugar counts 2.5 times as much). Fibre adds up to 10. Additives lose 0, 4 or 8 by risk level, 2 for an E-number we do not know yet (capped at 20 in total). Sugar in the first three ingredients (8 to 15), many sugar names, hydrogenated fat, palm oil and processing markers such as flavours, colours and sweeteners lose points too.

Ceilings stop a product scoring well on missing data or on its category: no nutrition table read caps the score at 55 (marked provisional), a drink with 8 g or more sugar per 100 ml is capped at grade E, 5 g or more at D, and other flavoured or sweetened soft drinks at C. The report lists every deduction under "Where the points went". Weights live in `nutrient_benchmarks` and `app/analysis.py`; extra additives are in `app/reference_extra.py` and are merged into existing databases on start-up.

## Known limits

- OCR works best on flat, well-lit, straight-on photos. Each photo is read several ways (different layouts, cleanup, rotation) and the best reading is kept. If it still misreads, edit the extracted text and re-run.
- A photo of only the ingredient list gives a provisional score. Add the nutrition table (second photo or paste text) for a full one.
- Per-serving-only labels are flagged as low confidence.
- Barcode lookup checks the local `products` table first, then queries Open Food Facts live (needs internet) and caches the result. Products missing from Open Food Facts need a label photo. Seeded products with source `demo` are fake.
- Barcode reading from photos uses `zxing-cpp` (installed by requirements.txt, no extra system library needed).
- If Tesseract is installed in a non-standard place, set the `TESSERACT_CMD` environment variable to the full path of tesseract(.exe).
- Re-running `init_db.py` resets all tables, including scan history.

## Data source

Product data seeded by `import_off.py` comes from Open Food Facts (openfoodfacts.org), available under the Open Database Licence (ODbL). Barcodes not found locally are fetched live from Open Food Facts and cached in the local products table.
