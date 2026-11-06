import re

from .parser import E_NUMBER_RE, extract_e_numbers, split_ingredients

NUTRIENT_KEYS = {
    "sugars": ("added_sugars_g", "sugars_g"),
    "sodium": ("sodium_mg",),
    "sat_fat": ("sat_fat_g",),
    "trans_fat": ("trans_fat_g",),
    "fibre": ("fibre_g",),
}

RISK_PENALTY = {"high": 8, "moderate": 4, "low": 0, "unknown": 2}
ADDITIVE_PENALTY_CAP = 20
GRADES = ((80, "A"), (65, "B"), (50, "C"), (35, "D"), (0, "E"))

BEVERAGE_FACTOR = 2.5          # drinks are consumed by the glass, so sugar per 100 ml counts more
SUGAR_POSITION_PENALTY = {0: 15, 1: 12, 2: 8}
PROCESSING_TERMS = (
    "flavour", "flavor", "flavouring", "nature identical", "artificial", "maltodextrin", "modified starch",
    "hydrolysed", "hydrolyzed", "emulsifier", "stabiliser", "stabilizer", "sweetener", "flavour enhancer",
    "colour", "color", "preservative", "anticaking", "anti-caking", "humectant", "thickener", "gelling agent",
    "glazing agent", "caramel", "protein isolate", "high fructose",
)
PROCESSING_PENALTY_EACH = 2
PROCESSING_PENALTY_CAP = 10
UNKNOWN_ADDITIVE_NOTE = "Not in our reference table yet; treated as a small concern until checked."
BEVERAGE_NAME_HINTS = ("cola", "soda", "soft drink", "drink", "juice", "beverage", "squash", "lemonade", "energy", "shake", "cooler")
WATER_FIRST = re.compile(r"^(?:carbonated|aerated|soda|sparkling|filtered|drinking|mineral|purified|packaged)?\s*(?:drinking\s+)?water\b")
SWEETENER_CODES = {"E420", "E421", "E950", "E951", "E952", "E954", "E955", "E960", "E965", "E967"}


def load_reference(conn):
    return {
        "benchmarks": {r["nutrient"]: dict(r) for r in conn.execute("SELECT * FROM nutrient_benchmarks")},
        "additives": [dict(r) for r in conn.execute("SELECT * FROM additives")],
        "allergens": [dict(r) for r in conn.execute("SELECT * FROM allergens")],
        "flags": [dict(r) for r in conn.execute("SELECT * FROM ingredient_flags")],
    }


def _word_match(term, text):
    return re.search(r"\b" + re.escape(term) + r"s?\b", text) is not None


def find_additives(text, ref):
    lowered = text.lower()
    found = {}
    codes = {"E" + m.group(1).lower() for m in E_NUMBER_RE.finditer(text)}
    for additive in ref["additives"]:
        code = additive["e_number"].lower()
        name = additive["name"].lower()
        name = re.sub(r"\s*\(.*?\)", "", name)
        if code in {c.lower() for c in codes} or _word_match(name, lowered):
            found[additive["e_number"]] = additive
    return list(found.values())


def find_allergens(text, ref):
    lowered = text.lower()
    hits = {}
    for row in ref["allergens"]:
        if _word_match(row["keyword"], lowered):
            hits.setdefault(row["name"], row["keyword"])
    return hits


def find_flags(ingredients, ref):
    results = {"sugar": [], "trans_fat_risk": [], "palm_oil": []}
    first_sugar_index = None
    for index, item in enumerate(ingredients):
        lowered = item.lower()
        matched = None
        for flag in sorted(ref["flags"], key=lambda f: -len(f["term"])):
            if _word_match(flag["term"], lowered):
                matched = flag
                break
        if matched:
            results[matched["flag"]].append({"ingredient": item, "position": index + 1, "note": matched["note"]})
            if matched["flag"] == "sugar" and first_sugar_index is None:
                first_sugar_index = index
    return results, first_sugar_index


def _nutrient_value(nutrients, nutrient):
    for key in NUTRIENT_KEYS[nutrient]:
        if key in nutrients:
            return nutrients[key], key
    return None, None


def grade_for(score):
    for floor, letter in GRADES:
        if score >= floor:
            return letter
    return "E"


def is_beverage(parsed, ingredients):
    if parsed.get("liquid"):
        return True
    first = (ingredients[0] if ingredients else "").lower().strip()
    if WATER_FIRST.match(first):
        return True
    name = (parsed.get("name_hint") or "").lower()
    return any(hint in name for hint in BEVERAGE_NAME_HINTS)


def analyze(parsed, ref):
    ingredients = parsed.get("ingredients") or []
    if not ingredients and parsed.get("ingredients_text"):
        ingredients = split_ingredients(parsed["ingredients_text"])
    ingredients_text = parsed.get("ingredients_text") or ", ".join(ingredients)
    nutrients = parsed.get("nutrients") or {}
    basis = parsed.get("basis", "per_100g")
    beverage = is_beverage(parsed, ingredients)
    unit_label = "100 ml" if beverage else "100 g"

    score = 100.0
    breakdown = []
    insights = []
    missing = []
    deductions = []

    for nutrient, bench in ref["benchmarks"].items():
        value, source_key = _nutrient_value(nutrients, nutrient)
        if value is None:
            missing.append(bench["label"])
            continue
        percent = value / bench["daily_value"] * 100
        if bench["kind"] == "limit":
            weight = percent * (BEVERAGE_FACTOR if (beverage and nutrient == "sugars") else 1)
            penalty = min(bench["max_penalty"], weight * 0.6)
            score -= penalty
            effect = -round(penalty, 1)
            if penalty >= bench["max_penalty"] * 0.6:
                level = "high"
            elif penalty >= bench["max_penalty"] * 0.25:
                level = "medium"
            else:
                level = "low"
            extra = " Drinks are scored more strictly for sugar because they are consumed in large volumes." if (beverage and nutrient == "sugars") else ""
            insights.append({
                "type": "nutrient",
                "level": level,
                "text": f"{bench['label']}: {value:g} {bench['unit']} per {unit_label}, about {percent:.0f}% of the WHO daily limit ({bench['daily_value']:g} {bench['unit']}).{extra}",
            })
            if round(penalty, 1) > 0:
                deductions.append({"label": bench["label"], "points": effect, "kind": "nutrient"})
        else:
            bonus = min(bench["max_bonus"], percent * 0.4)
            score += bonus
            effect = round(bonus, 1)
            level = "good" if percent >= 12 else "low"
            insights.append({
                "type": "nutrient",
                "level": level,
                "text": f"{bench['label']}: {value:g} {bench['unit']} per {unit_label}, about {percent:.0f}% of the WHO daily target ({bench['daily_value']:g} {bench['unit']}).",
            })
            if effect > 0:
                deductions.append({"label": bench["label"], "points": effect, "kind": "bonus"})
        breakdown.append({
            "nutrient": nutrient,
            "value": value,
            "unit": bench["unit"],
            "percent_of_daily": round(percent, 1),
            "score_effect": effect,
            "used_field": source_key,
        })

    additive_text = ingredients_text + " " + " ".join(parsed.get("e_numbers") or [])
    additives = find_additives(additive_text, ref)
    known = {a["e_number"].lower() for a in additives}
    unknown_codes = [c for c in extract_e_numbers(additive_text) if c.lower() not in known and not any(k.startswith(c.lower()) for k in known)]
    additive_penalty = sum(RISK_PENALTY[a["risk"]] for a in additives) + RISK_PENALTY["unknown"] * len(unknown_codes)
    additive_penalty = min(ADDITIVE_PENALTY_CAP, additive_penalty)
    score -= additive_penalty
    if additive_penalty:
        deductions.append({"label": f"Additives ({len(additives) + len(unknown_codes)} found)", "points": -additive_penalty, "kind": "additive"})
    additive_out = []
    for additive in additives:
        additive_out.append({
            "e_number": additive["e_number"],
            "name": additive["name"],
            "category": additive["category"],
            "risk": additive["risk"],
            "note": additive["note"],
        })
        if additive["risk"] != "low":
            insights.append({
                "type": "additive",
                "level": additive["risk"],
                "text": f"{additive['name']} ({additive['e_number']}), a {additive['category']}: {additive['note']}",
            })
    for code in unknown_codes:
        additive_out.append({"e_number": code, "name": "Additive " + code, "category": "additive", "risk": "unknown", "note": UNKNOWN_ADDITIVE_NOTE})

    flags, first_sugar_index = find_flags(ingredients, ref)
    ingredient_penalty = 0

    def charge(label, points):
        nonlocal ingredient_penalty
        ingredient_penalty += points
        deductions.append({"label": label, "points": -points, "kind": "ingredient"})

    if first_sugar_index is not None and first_sugar_index in SUGAR_POSITION_PENALTY:
        charge(f"Sugar listed in position {first_sugar_index + 1}", SUGAR_POSITION_PENALTY[first_sugar_index])
        insights.append({
            "type": "ingredient",
            "level": "high",
            "text": f"A sugar ingredient is listed in position {first_sugar_index + 1}, so sugar makes up a large share of this product.",
        })
    if len(flags["sugar"]) >= 3:
        charge("Several sugar names", 3)
        insights.append({
            "type": "ingredient",
            "level": "medium",
            "text": f"{len(flags['sugar'])} different sugar ingredients are listed, which can hide how much sugar there really is.",
        })
    if flags["trans_fat_risk"]:
        charge("Hydrogenated fat", 5)
        insights.append({
            "type": "ingredient",
            "level": "high",
            "text": "Hydrogenated or vanaspati-type fat is listed, which can contain trans fat even when the label says 0 g.",
        })
    if flags["palm_oil"]:
        charge("Palm oil", 2)
        insights.append({
            "type": "ingredient",
            "level": "medium",
            "text": "Palm oil is used, which is high in saturated fat.",
        })

    lowered_ingredients = ingredients_text.lower()
    markers = sorted({t for t in PROCESSING_TERMS if re.search(r"\b" + re.escape(t) + r"s?\b", lowered_ingredients)})
    if markers:
        processing = min(PROCESSING_PENALTY_CAP, PROCESSING_PENALTY_EACH * len(markers))
        charge("Heavily processed markers", processing)
        insights.append({
            "type": "ingredient",
            "level": "medium" if processing < 6 else "high",
            "text": "Ingredients typical of ultra-processed food: " + ", ".join(markers) + ".",
        })
    score -= ingredient_penalty

    contains_text = (ingredients_text + " " + (parsed.get("contains_text") or "")).strip()
    contains = find_allergens(contains_text, ref)
    traces = {
        name: keyword
        for name, keyword in find_allergens(parsed.get("trace_text") or "", ref).items()
        if name not in contains
    }
    if contains:
        insights.append({"type": "allergen", "level": "high", "text": "Contains: " + ", ".join(sorted(contains)) + "."})
    if traces:
        insights.append({"type": "allergen", "level": "medium", "text": "May contain traces of: " + ", ".join(sorted(traces)) + "."})

    # Score ceilings: a product cannot be rated well on what is missing or on what the category is.
    caps = []
    key_found = [n for n in ("sugars", "sodium", "sat_fat") if _nutrient_value(nutrients, n)[0] is not None]
    if not key_found:
        caps.append((55, "No nutrition table was read, so this score rests on the ingredient list alone."))
    elif len(key_found) < 3:
        caps.append((75, "Part of the nutrition table is missing, so the score cannot be top grade."))
    sugar_value = _nutrient_value(nutrients, "sugars")[0]
    sweetener_hit = any(a["e_number"] in SWEETENER_CODES or a["category"] == "sweetener" for a in additives)
    sugar_listed_early = first_sugar_index is not None and first_sugar_index < 3
    if beverage:
        if sugar_value is not None and sugar_value >= 8:
            caps.append((34, f"A drink with {sugar_value:g} g sugar per 100 ml is a high-sugar drink."))
        elif sugar_value is not None and sugar_value >= 5:
            caps.append((49, f"A drink with {sugar_value:g} g sugar per 100 ml is a sugary drink."))
        elif sugar_value is None and sugar_listed_early:
            caps.append((49, "Sugar is a main ingredient of this drink, so it is treated as a sugary drink."))
        elif sweetener_hit or markers or additives:
            caps.append((64, "Flavoured or sweetened soft drinks are not rated above C, even without sugar."))
    cap_note = None
    if caps:
        limit, reason = min(caps)
        if score > limit:
            deductions.append({"label": "Score ceiling", "points": -round(score - limit), "kind": "cap"})
            score = limit
            cap_note = {"limit": limit, "reason": reason}
            insights.append({"type": "ingredient", "level": "high", "text": reason})

    confidence = "high"
    notes = []
    if basis == "per_serving":
        confidence = "low"
        notes.append("The label shows values per serving, not per 100 g, so the benchmark comparison may be off.")
    if missing:
        confidence = "low" if len(missing) >= 3 else "medium"
        notes.append("Missing nutrition values: " + ", ".join(missing) + ". Score uses the data that was found.")
    if not ingredients:
        confidence = "low"
        notes.append("No ingredient list was found, so additive and allergen checks were skipped.")
    provisional = not key_found
    if provisional:
        notes.append("Provisional score: photograph or enter the nutrition table as well for a full result.")
    if cap_note:
        notes.append(cap_note["reason"])

    final_score = int(round(max(0, min(100, score))))
    grade = grade_for(final_score)
    deductions.sort(key=lambda d: d["points"])

    return {
        "score": final_score,
        "grade": grade,
        "summary": _summary(final_score, grade, insights, beverage, provisional),
        "confidence": confidence,
        "notes": notes,
        "nutrients": breakdown,
        "additives": additive_out,
        "allergens": {"contains": sorted(contains), "may_contain": sorted(traces)},
        "ingredient_flags": flags,
        "insights": insights,
        "ingredients": ingredients,
        "deductions": deductions,
        "basis_label": unit_label,
        "category": "beverage" if beverage else "food",
        "provisional": provisional,
        "cap": cap_note,
    }


def _summary(score, grade, insights, beverage=False, provisional=False):
    high = [i for i in insights if i["level"] == "high" and i["type"] != "allergen"]
    if grade in ("A", "B"):
        lead = "A reasonable everyday choice."
    elif grade == "C":
        lead = "Fine occasionally, but not an everyday food."
    else:
        lead = "Best kept as an occasional treat."
    if beverage and grade in ("C", "D", "E"):
        lead = "A soft drink: " + lead[0].lower() + lead[1:]
    if high:
        lead += f" {len(high)} major concern{'s' if len(high) != 1 else ''} flagged."
    tag = " Provisional, from the ingredient list only." if provisional else ""
    return f"Health score {score}/100 (grade {grade}). {lead}{tag}"
