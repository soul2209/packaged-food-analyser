import json

from flask import Blueprint, jsonify, render_template, request

from . import analysis, content, ocr, parser, products
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


def _save_scan(conn, barcode, input_type, result):
    cursor = conn.execute(
        "INSERT INTO scans (barcode, input_type, score, grade, result_json) VALUES (?, ?, ?, ?, ?)",
        (barcode, input_type, result["score"], result["grade"], json.dumps(result)),
    )
    conn.commit()
    return cursor.lastrowid


def _run(conn, parsed, barcode, input_type, extra=None):
    ref = analysis.load_reference(conn)
    result = analysis.analyze(parsed, ref)
    if extra:
        result.update(extra)
    result["scan_id"] = _save_scan(conn, barcode, input_type, result)
    return result


def _title(result):
    product = result.get("product") or {}
    if product.get("name"):
        return product["name"]
    items = result.get("ingredients") or []
    if items:
        return ", ".join(items[:3])
    return "Untitled scan"


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/reference")
def reference():
    ref = analysis.load_reference(get_db())
    return jsonify({"benchmarks": list(ref["benchmarks"].values())})


@bp.post("/analyze/text")
def analyze_text():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or request.form.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Send label text in the 'text' field."}), 400
    parsed = parser.parse_label(text)
    return jsonify(_run(get_db(), parsed, None, "text", {"extracted": parsed}))


@bp.post("/analyze/preview")
def analyze_preview():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Send label text in the 'text' field."}), 400
    parsed = parser.parse_label(text)
    return jsonify(analysis.analyze(parsed, analysis.load_reference(get_db())))


def _quality(parsed):
    ingredients = parsed["ingredients"]
    return (3 if ingredients else 0) + min(len(ingredients), 12) * 0.5 + len(parsed["nutrients"]) * 1.0


def _good_enough(parsed):
    return len(parsed["ingredients"]) >= 4 and len(parsed["nutrients"]) >= 3


def _best_reading(data):
    """Try several OCR passes; keep the best parse and fill gaps from the others."""
    best_text, best, best_q = "", None, -1
    nutrients_pool, seen = {}, []
    for stage in (ocr.extract_candidates, ocr.extract_rotated):
        if stage is ocr.extract_rotated and best is not None and _quality(best) >= 4:
            break
        for text in stage(data):
            seen.append(text)
            parsed = parser.parse_label(text)
            for key, value in parsed["nutrients"].items():
                nutrients_pool.setdefault(key, value)
            quality = _quality(parsed)
            if quality > best_q:
                best_text, best, best_q = text, parsed, quality
            if _good_enough(parsed):
                return best_text, best
    if best is not None:
        for key, value in nutrients_pool.items():
            best["nutrients"].setdefault(key, value)
    return best_text, best


@bp.post("/analyze/image")
def analyze_image():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "Upload a label photo in the 'image' field."}), 400
    data = file.read()

    typed = "".join(ch for ch in request.form.get("barcode", "") if ch.isdigit())
    barcode = typed or ocr.decode_barcode(data)

    ocr_error = None
    text, parsed = "", None
    try:
        text, parsed = _best_reading(data)
    except ocr.OcrUnavailable:
        ocr_error = "ocr_missing"
    except Exception:
        ocr_error = "unreadable"

    if parsed and (parsed["ingredients"] or parsed["nutrients"]):
        extra = {"extracted": parsed, "ocr_text": text}
        return jsonify(_run(get_db(), parsed, barcode, "image", extra))

    # No usable label text: if the photo holds a barcode, fall back to a product lookup.
    if barcode and products.valid_gtin(barcode):
        body, status = _barcode_report(barcode)
        if status == 200:
            body["detected_barcode"] = barcode
            return jsonify(body)

    if ocr_error == "ocr_missing":
        return jsonify({"error": "Text reading (Tesseract OCR) is not installed on the server. Install Tesseract, or set TESSERACT_CMD to its path, then restart. Meanwhile use the Barcode or Paste text tab."}), 503
    if ocr_error == "unreadable":
        return jsonify({"error": "Could not read that image. Try a clearer, well-lit photo."}), 422
    return jsonify({"error": "No ingredients or nutrition table found in the image. Photograph the ingredient list or the nutrition table straight-on, with the text filling the frame.", "ocr_text": text}), 422


@bp.app_errorhandler(413)
def too_large(error):
    return jsonify({"error": "That file is too large. Use a photo under 8 MB."}), 413


def _barcode_report(code):
    """Look up a barcode and return (response_json, status)."""
    code = "".join(ch for ch in code if ch.isdigit())
    if not products.valid_gtin(code):
        return {"error": "That barcode is not a valid EAN/UPC number."}, 400
    conn = get_db()
    product, error, status = products.lookup_barcode(conn, code)
    if error:
        return {"error": error}, status
    parsed = {
        "ingredients_text": product["ingredients_text"],
        "ingredients": parser.split_ingredients(product["ingredients_text"]) if product["ingredients_text"] else [],
        "contains_text": "",
        "trace_text": "",
        "e_numbers": parser.extract_e_numbers(product["ingredients_text"]),
        "nutrients": product["nutrients"],
        "basis": "per_100g",
        "name_hint": product["name"],
    }
    extra = {"product": {"barcode": product["barcode"], "name": product["name"], "brand": product["brand"], "source": product["source"]}}
    return _run(conn, parsed, product["barcode"], "barcode", extra), 200


@bp.get("/analyze/barcode/<code>")
def analyze_barcode(code):
    body, status = _barcode_report(code)
    return jsonify(body), status


@bp.post("/analyze/barcode-image")
def analyze_barcode_image():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "Upload a barcode photo in the 'image' field."}), 400
    data = file.read()
    code = ocr.decode_barcode(data)
    if not code:
        return jsonify({"error": "No barcode could be read in that photo. Make the barcode fill the frame, keep it flat and sharp, or type the number instead."}), 422
    body, status = _barcode_report(code)
    body["detected_barcode"] = code
    if status != 200:
        body["error"] = f"Barcode {code} read from the photo. " + body.get("error", "")
    return jsonify(body), status


@bp.get("/products")
def product_list():
    return jsonify(products.list_products(get_db()))


@bp.get("/scans")
def scans():
    rows = get_db().execute(
        "SELECT id, barcode, input_type, score, grade, created_at, result_json FROM scans ORDER BY id DESC LIMIT 50"
    ).fetchall()
    out = []
    for row in rows:
        item = {k: row[k] for k in ("id", "barcode", "input_type", "score", "grade", "created_at")}
        item["title"] = _title(json.loads(row["result_json"]))
        out.append(item)
    return jsonify(out)


@bp.get("/scans/<int:scan_id>")
def scan_detail(scan_id):
    row = get_db().execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not row:
        return jsonify({"error": "Scan not found."}), 404
    result = json.loads(row["result_json"])
    result["scan_id"] = row["id"]
    result["created_at"] = row["created_at"]
    return jsonify(result)


@bp.delete("/scans/<int:scan_id>")
def scan_delete(scan_id):
    conn = get_db()
    cursor = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.commit()
    if cursor.rowcount == 0:
        return jsonify({"error": "Scan not found."}), 404
    return jsonify({"deleted": scan_id})


pages = Blueprint("pages", __name__)


@pages.get("/")
def index():
    conn = get_db()
    ref = analysis.load_reference(conn)
    limits = [b for b in ref["benchmarks"].values() if b["kind"] == "limit"]
    targets = [b for b in ref["benchmarks"].values() if b["kind"] == "target"]
    stats = {
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "additives": len(ref["additives"]),
        "allergen_terms": len(ref["allergens"]),
        "sugar_names": sum(1 for f in ref["flags"] if f["flag"] == "sugar"),
    }
    grades = []
    ceiling = 100
    for floor, letter in analysis.GRADES:
        grades.append({"letter": letter, "low": floor, "high": ceiling})
        ceiling = floor - 1
    return render_template(
        "home.html",
        limits=limits,
        targets=targets,
        stats=stats,
        grades=grades,
        risk_penalty=analysis.RISK_PENALTY,
        additive_cap=analysis.ADDITIVE_PENALTY_CAP,
        ingredient_rules=content.INGREDIENT_RULES,
        team=content.TEAM,
        about=content.ABOUT,
    )


@pages.get("/analyze")
def analyze_page():
    return render_template("analyze.html")


@pages.get("/history")
def history():
    return render_template("history.html")


@pages.get("/report/<int:scan_id>")
def report(scan_id):
    return render_template("report.html", scan_id=scan_id)


@pages.get("/compare")
def compare():
    return render_template("compare.html")
