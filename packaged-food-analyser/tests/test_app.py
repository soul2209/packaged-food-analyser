import io
from pathlib import Path

import pytest

from app import analysis, create_app, parser
from app.db import connect, init_db
from app.products import valid_gtin

SAMPLE = (Path(__file__).parent.parent / "sample" / "label_sample.txt").read_text()
SAMPLE_PNG = Path(__file__).parent.parent / "sample" / "label_sample.png"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    init_db(str(path))
    return str(path)


@pytest.fixture
def ref(db_path):
    conn = connect(db_path)
    yield analysis.load_reference(conn)
    conn.close()


@pytest.fixture
def client(db_path):
    app = create_app({"DATABASE": db_path, "TESTING": True})
    return app.test_client()


def test_split_ingredients_respects_brackets():
    items = parser.split_ingredients("Flour (wheat, barley), Sugar, Raising agents (E500, E450).")
    assert items == ["Flour (wheat, barley)", "Sugar", "Raising agents (E500, E450)"]


def test_parse_label_sample():
    parsed = parser.parse_label(SAMPLE)
    assert parsed["e_numbers"] == ["E102", "E322", "E450", "E500"]
    assert parsed["nutrients"]["sugars_g"] == 31.0
    assert parsed["nutrients"]["added_sugars_g"] == 29.0
    assert parsed["nutrients"]["sodium_mg"] == 410.0
    assert "Peanuts" in parsed["trace_text"]


def test_nutrient_unit_conversion():
    nutrients, _ = parser.parse_nutrients("Energy 2092 kJ\nSodium 0.4 g\nFibre 3,5 g")
    assert round(nutrients["energy_kcal"]) == 500
    assert nutrients["sodium_mg"] == 400
    assert nutrients["fibre_g"] == 3.5


def test_salt_converted_to_sodium():
    nutrients, _ = parser.parse_nutrients("Salt 1.5 g")
    assert nutrients["sodium_mg"] == 600


def test_biscuit_scores_low_and_flags_everything(ref):
    result = analysis.analyze(parser.parse_label(SAMPLE), ref)
    assert result["grade"] in ("D", "E")
    assert result["allergens"]["contains"] == ["Milk", "Soy", "Wheat and gluten"]
    assert result["allergens"]["may_contain"] == ["Peanuts", "Tree nuts"]
    assert any(a["e_number"] == "E102" for a in result["additives"])
    assert any(i["type"] == "ingredient" and "position 2" in i["text"] for i in result["insights"])


def test_clean_product_scores_high(ref):
    parsed = {
        "ingredients_text": "Rolled oats, almonds",
        "ingredients": ["Rolled oats", "almonds"],
        "nutrients": {"sugars_g": 1, "sodium_mg": 5, "sat_fat_g": 1.2, "trans_fat_g": 0, "fibre_g": 10},
        "basis": "per_100g",
    }
    result = analysis.analyze(parsed, ref)
    assert result["score"] >= 90
    assert result["grade"] == "A"
    assert result["allergens"]["contains"] == ["Tree nuts"]


def test_missing_nutrients_lowers_confidence(ref):
    parsed = {"ingredients_text": "Water, sugar", "ingredients": ["Water", "sugar"], "nutrients": {}}
    result = analysis.analyze(parsed, ref)
    assert result["confidence"] == "low"
    assert result["notes"]


def test_score_is_bounded(ref):
    parsed = {
        "ingredients_text": "Sugar, glucose syrup, fructose, vanaspati, E102, E110, E122, E129, E250",
        "nutrients": {"sugars_g": 90, "sodium_mg": 4000, "sat_fat_g": 40, "trans_fat_g": 5, "fibre_g": 0},
    }
    result = analysis.analyze(parsed, ref)
    assert 0 <= result["score"] <= 100
    assert result["grade"] == "E"


def test_valid_gtin():
    assert valid_gtin("4006381333931") is True
    assert valid_gtin("4006381333932") is False
    assert valid_gtin("1234") is False
    assert valid_gtin("abcdefgh") is False


def test_api_text_and_scans(client):
    response = client.post("/api/analyze/text", json={"text": SAMPLE})
    assert response.status_code == 200
    body = response.get_json()
    assert body["grade"] in ("D", "E")
    scans = client.get("/api/scans").get_json()
    assert scans[0]["input_type"] == "text"


def test_api_text_requires_text(client):
    assert client.post("/api/analyze/text", json={}).status_code == 400


def test_api_barcode_rejects_bad_code(client):
    assert client.get("/api/analyze/barcode/123").status_code == 400


def test_api_image_ocr_pipeline(client):
    if not SAMPLE_PNG.exists():
        pytest.skip("sample image missing")
    response = client.post(
        "/api/analyze/image",
        data={"image": (io.BytesIO(SAMPLE_PNG.read_bytes()), "label.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["extracted"]["nutrients"]["sodium_mg"] == 410.0
    assert body["grade"] in ("D", "E")


def test_api_image_missing(client):
    assert client.post("/api/analyze/image").status_code == 400


def test_api_image_not_an_image(client):
    response = client.post(
        "/api/analyze/image",
        data={"image": (io.BytesIO(b"not an image"), "x.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert "error" in response.get_json()


def test_api_image_too_large(db_path):
    app = create_app({"DATABASE": db_path, "TESTING": True, "MAX_CONTENT_LENGTH": 1000})
    response = app.test_client().post(
        "/api/analyze/image",
        data={"image": (io.BytesIO(b"x" * 5000), "big.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413
    assert "too large" in response.get_json()["error"]


def test_scan_detail_and_delete(client):
    created = client.post("/api/analyze/text", json={"text": SAMPLE}).get_json()
    scan_id = created["scan_id"]
    detail = client.get(f"/api/scans/{scan_id}")
    assert detail.status_code == 200
    assert detail.get_json()["score"] == created["score"]
    assert client.delete(f"/api/scans/{scan_id}").status_code == 200
    assert client.get(f"/api/scans/{scan_id}").status_code == 404
    assert client.delete(f"/api/scans/{scan_id}").status_code == 404


def test_history_titles(client):
    client.post("/api/analyze/text", json={"text": SAMPLE})
    scans = client.get("/api/scans").get_json()
    assert scans[0]["title"].startswith("Refined wheat flour")


@pytest.mark.parametrize("url", ["/", "/analyze", "/history", "/compare", "/report/1"])
def test_pages_render(client, url):
    assert client.get(url).status_code == 200


def test_per_serving_first_column_uses_per_100g_value():
    text = (
        "Nutrition Information\n"
        "Per serving | Per 100 g\n"
        "Energy 120 kcal 400 kcal\n"
        "Sugars 6 g 20 g\n"
        "Sodium 90 mg 300 mg\n"
    )
    nutrients, basis = parser.parse_nutrients(text)
    assert basis == "per_100g"
    assert nutrients["sugars_g"] == 20
    assert nutrients["sodium_mg"] == 300


def test_serving_size_line_does_not_flip_columns():
    text = "Nutrition Information\nServing size 30 g\nPer 100 g | Per serving\nSugars 20 g 6 g\n"
    nutrients, _ = parser.parse_nutrients(text)
    assert nutrients["sugars_g"] == 20


def test_per_serving_only_is_flagged():
    nutrients, basis = parser.parse_nutrients("Nutrition Facts per serving\nSugars 6 g\n")
    assert basis == "per_serving"


def test_nil_values_become_zero():
    nutrients, _ = parser.parse_nutrients("Nutrition Information\nTrans Fat Nil\nSugars 3 g\n")
    assert nutrients["trans_fat_g"] == 0.0


def test_misspelled_ingredients_heading():
    parsed = parser.parse_label("Ingredlents: Sugar, Salt\nEnergy 100 kcal")
    assert parsed["ingredients"] == ["Sugar", "Salt"]


def test_barcode_input_is_cleaned(client):
    assert client.get("/api/analyze/barcode/12-34").status_code == 400


def test_barcode_lookup_uses_local_database(client):
    response = client.get("/api/analyze/barcode/2000000100005")
    assert response.status_code == 200
    body = response.get_json()
    assert body["product"]["name"] == "Demo Choco Cream Biscuits"
    assert body["product"]["source"] == "demo"
    assert client.get("/api/scans").get_json()[0]["input_type"] == "barcode"


def _off(monkeypatch, result=None, error=False):
    from app import products

    def fake(barcode, timeout=10):
        if error:
            raise products.LookupUnavailable("offline")
        return result

    monkeypatch.setattr(products, "fetch_from_off", fake)


def test_unknown_barcode_points_to_label_scan(client, monkeypatch):
    _off(monkeypatch, None)
    response = client.get("/api/analyze/barcode/4006381333931")
    assert response.status_code == 404
    assert "Photograph the label" in response.get_json()["error"]


def test_unknown_barcode_is_fetched_from_open_food_facts_and_cached(client, monkeypatch):
    product = {"barcode": "4006381333931", "name": "Live Biscuit", "brand": "Acme",
               "ingredients_text": "Sugar, Palm oil, Wheat flour", "nutrients": {"sugars_g": 20.0, "sodium_mg": 300.0},
               "source": "openfoodfacts"}
    _off(monkeypatch, product)
    first = client.get("/api/analyze/barcode/4006381333931")
    assert first.status_code == 200
    assert first.get_json()["product"]["name"] == "Live Biscuit"
    _off(monkeypatch, error=True)  # second time must come from the local cache
    assert client.get("/api/analyze/barcode/4006381333931").status_code == 200


def test_barcode_lookup_reports_network_failure(client, monkeypatch):
    _off(monkeypatch, error=True)
    response = client.get("/api/analyze/barcode/4006381333931")
    assert response.status_code == 503
    assert "Open Food Facts" in response.get_json()["error"]


def test_seeded_barcodes_are_valid(client):
    for item in client.get("/api/products").get_json():
        assert valid_gtin(item["barcode"])


def test_home_page_shows_real_reference_data(client):
    html = client.get("/").get_data(as_text=True)
    assert "Tap the ingredient" in html
    assert "WHO daily value" in html
    assert "Sugars" in html


def test_preview_scores_without_saving(client):
    before = client.get("/api/scans").get_json()
    response = client.post("/api/analyze/preview", json={"text": "Ingredients: Sugar, Palm oil, Colour (E102).\nSodium 300 mg"})
    assert response.status_code == 200
    body = response.get_json()
    assert 0 <= body["score"] <= 100
    assert body["additives"][0]["e_number"] == "E102"
    assert client.get("/api/scans").get_json() == before


def test_preview_requires_text(client):
    assert client.post("/api/analyze/preview", json={}).status_code == 400


BARCODE_PNG = Path(__file__).parent / "barcode_sample.png"


def test_decode_barcode_from_image():
    from app import ocr
    assert ocr.decode_barcode(BARCODE_PNG.read_bytes()) == "8901058852608"


def test_barcode_image_endpoint(client, monkeypatch):
    product = {"barcode": "8901058852608", "name": "Live Noodles", "brand": "Acme",
               "ingredients_text": "Wheat flour, Palm oil, Salt", "nutrients": {"sodium_mg": 900.0},
               "source": "openfoodfacts"}
    _off(monkeypatch, product)
    response = client.post("/api/analyze/barcode-image", data={"image": (io.BytesIO(BARCODE_PNG.read_bytes()), "b.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.get_json()["product"]["name"] == "Live Noodles"


def test_barcode_image_without_barcode_gives_clear_error(client):
    response = client.post("/api/analyze/barcode-image", data={"image": (io.BytesIO(SAMPLE_PNG.read_bytes()), "l.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 422
    assert "No barcode" in response.get_json()["error"]


def test_product_without_data_gets_specific_message(client, monkeypatch):
    _off(monkeypatch, {"barcode": "4006381333931", "name": "Empty Thing", "brand": "", "ingredients_text": "",
                       "nutrients": {}, "source": "openfoodfacts"})
    response = client.get("/api/analyze/barcode/4006381333931")
    assert response.status_code == 422
    assert "Empty Thing" in response.get_json()["error"]


def test_photo_of_barcode_in_label_tab_falls_back_to_lookup(client, monkeypatch):
    product = {"barcode": "8901058852608", "name": "Live Noodles", "brand": "", "ingredients_text": "Wheat flour, Salt",
               "nutrients": {"sodium_mg": 900.0}, "source": "openfoodfacts"}
    _off(monkeypatch, product)
    response = client.post("/api/analyze/image", data={"image": (io.BytesIO(BARCODE_PNG.read_bytes()), "b.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.get_json()["product"]["name"] == "Live Noodles"


COKE_ING = "INGREDIENTS\nCarbonated Water, Sugar, Acidity Regulator (338),\nCaffeine, Added Natural Flavours (Contains Caramel)\nColour (150d)"
COKE_FULL = ("Ingredients: Carbonated Water, Sugar, Caramel Colour E150d, Acidity Regulator (E338), Caffeine\n"
             "Nutrition Facts (per 100 ml)\nEnergy 180 kJ / 42 kcal\nFat 0 g\nCarbohydrate 10.6 g\nof which sugars 10.6 g\nProtein 0 g\nSalt 0 g")
CHIPS = ("Ingredients: Potato, Edible vegetable oil (Palmolein), Salt, Flavour enhancer (INS 627, INS 631), Maltodextrin\n"
         "Nutrition per 100g: Energy 536 kcal Protein 6.5g Carbohydrate 53g Total Sugar 1.5g Total Fat 34g "
         "Saturated Fat 15g Trans Fat 0.1g Sodium 700mg")


def test_ingredients_heading_without_colon_is_read():
    parsed = parser.parse_label(COKE_ING)
    assert parsed["ingredients"][:2] == ["Carbonated Water", "Sugar"]
    assert parsed["nutrients"] == {}          # the ingredient line must not be read as a sugar value
    assert "E338" in parsed["e_numbers"] and "E150d" in parsed["e_numbers"]


def test_inline_nutrition_is_read():
    nutrients = parser.parse_label(CHIPS)["nutrients"]
    assert nutrients["sodium_mg"] == 700 and nutrients["sat_fat_g"] == 15 and nutrients["fat_g"] == 34


def test_nutrition_table_with_unit_in_header():
    nutrients, _ = parser.parse_nutrients("Per 100 ml Per 250 ml\nEnergy (kcal) 42 105\nSugars (g) 10.6 26.5\nSodium (mg) 4 10")
    assert nutrients["sugars_g"] == 10.6 and nutrients["energy_kcal"] == 42 and nutrients["sodium_mg"] == 4


def test_cola_from_ingredients_only_is_not_an_A(ref):
    result = analysis.analyze(parser.parse_label(COKE_ING), ref)
    assert result["grade"] in ("D", "E")
    assert result["provisional"] is True
    assert result["category"] == "beverage"


def test_cola_with_nutrition_table_scores_E(ref):
    result = analysis.analyze(parser.parse_label(COKE_FULL), ref)
    assert result["grade"] == "E"
    assert result["basis_label"] == "100 ml"
    assert any(d["kind"] == "cap" for d in result["deductions"])


def test_salty_fried_snack_is_not_an_A(ref):
    result = analysis.analyze(parser.parse_label(CHIPS), ref)
    assert result["grade"] in ("D", "E")


def test_unknown_e_number_still_counts(ref):
    parsed = {"ingredients_text": "Wheat flour, Colour (INS 133 and INS 999)", "ingredients": [],
              "nutrients": {"sugars_g": 2, "sodium_mg": 100, "sat_fat_g": 1}, "e_numbers": []}
    result = analysis.analyze(parsed, ref)
    assert any(a["e_number"] == "E999" and a["risk"] == "unknown" for a in result["additives"])


def test_no_nutrition_caps_score(ref):
    result = analysis.analyze({"ingredients_text": "Rolled oats", "ingredients": ["Rolled oats"], "nutrients": {}}, ref)
    assert result["score"] <= 55


def _post_image(client, name):
    path = Path(__file__).parent / name
    return client.post("/api/analyze/image", data={"image": (io.BytesIO(path.read_bytes()), name)},
                       content_type="multipart/form-data")


def test_photo_of_cola_ingredients_scores_low(client):
    body = _post_image(client, "coke_ingredients.png").get_json()
    assert "Sugar" in [i.title() for i in body["ingredients"]] or "SUGAR" in body["ingredients"]
    assert body["grade"] in ("D", "E")
    assert body["deductions"]


def test_photo_of_cola_nutrition_table(client):
    body = _post_image(client, "coke_nutrition.png").get_json()
    assert body["extracted"]["nutrients"]["sugars_g"] == 10.6
    assert body["grade"] == "E"
