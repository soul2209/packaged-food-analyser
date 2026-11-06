import re

STOP_WORDS = (
    r"nutrition|nutritional|nutrient|allergen|contains(?!\s+(?:permitted|added|natural|nature|artificial|class|no\b|preserv|colou?r|flavou?r))|"
    r"may\s+contain|manufactured|marketed|distributed|imported|packed|best\s+before|use\s+by|mfd|mfg|batch|"
    r"net\s*(?:wt|weight|qty|quantity|vol|volume|content)|storage|store\s+in|fssai|mrp|directions|customer|consumer|"
    r"average|typical|per\s*100|serving|energy|calories|protein|total\s+fat|carbohydrate|sodium|"
    r"vegetarian|non[\s-]*veg|country\s+of\s+origin|made\s+in"
)

ING_HEAD_LINE = re.compile(r"(?im)^[ \t>*•\-]*(?:list\s+of\s+)?ingred\w{3,6}\b[ \t]*[:\-.]?[ \t]*")
ING_HEAD_INLINE = re.compile(r"(?i)ingred\w{3,6}\s*[:\-]\s*")
STOP_LINE = re.compile(r"(?im)^[ \t>*•\-]*(?:" + STOP_WORDS + r")\b")
STOP_INLINE = re.compile(r"(?i)\b(?:allergen\s+(?:information|advice)|may\s+contain|nutrition(?:al)?\s+(?:information|facts|value)|best\s+before|manufactured\s+by|marketed\s+by)\b")

CONTAINS_RE = re.compile(
    r"(?:^|\n)\s*(?:allergen\s*(?:information|advice)?\s*[:\-]?\s*)?contains\s*[:\-]?\s*([^\n]+)",
    re.IGNORECASE,
)
MAY_CONTAIN_RE = re.compile(r"may\s+contain\s*[:\-]?\s*([^\n.]+)", re.IGNORECASE)
E_NUMBER_RE = re.compile(r"\b(?:E|INS)\s?-?(\d{3,4}[a-i]?)\b", re.IGNORECASE)

CLASS_WORDS = (
    r"colou?rs?|acidity\s+regulators?|acidulants?|preservatives?|antioxidants?|emulsifiers?|stabili[sz]ers?|"
    r"thickeners?|sweeteners?|flavou?r\s+enhancers?|raising\s+agents?|anti[\s-]*caking\s+agents?|humectants?|"
    r"gelling\s+agents?|glazing\s+agents?|firming\s+agents?|bulking\s+agents?|flour\s+treatment\s+agents?|"
    r"foaming\s+agents?|propellants?|sequestrants?|acids?"
)
_CODE = r"(?:(?:INS|E)\s*-?\s*)?\d{3,4}[a-z]?(?:\s*\(?(?:iv|v?i{0,3}|vi{0,2}|ix|x)\)?)?"
PAREN_CODES_RE = re.compile(r"\(\s*(" + _CODE + r"(?:\s*(?:,|&|/|and)\s*" + _CODE + r")*)\s*\)", re.IGNORECASE)
CLASS_CODE_RE = re.compile(r"(?:" + CLASS_WORDS + r")\s*[:\-]?\s*(" + _CODE + r"(?:\s*(?:,|&|/|and)\s*" + _CODE + r")*)", re.IGNORECASE)
CODE_RE = re.compile(r"(?:INS|E)?\s*-?\s*(\d{3,4})([a-z])?(?:\s*\(?(iv|vi{0,2}|i{1,3}|ix|x)\)?)?", re.IGNORECASE)
ROMAN_150 = {"i": "a", "ii": "b", "iii": "c", "iv": "d"}

NUM = r"[<≤]?\s*(\d+(?:[.,]\d+)?)"
UNIT = r"(kcal|kj|mg|mcg|µg|μg|gm|g)"

# key, keywords (regex), words that, right before the keyword, mean it is a different nutrient
NUTRIENT_RULES = [
    ("added_sugars_g", r"(?:includes\s+)?added\s+sugars?|sugars?\s+added", ()),
    ("sugars_g", r"(?:total\s+|of\s+which\s+)?sugars?", ("added ", "no ", "low ", "free ")),
    ("sat_fat_g", r"saturated(?:\s+fat(?:ty\s+acids?)?)?|sat\.?\s*fat|saturates", ("un", "mono", "poly")),
    ("trans_fat_g", r"trans(?:\s*fat(?:ty\s+acids?)?)?", ()),
    ("fibre_g", r"(?:dietary\s+|total\s+)?fib(?:re|er)", ()),
    ("sodium_mg", r"sodium", ()),
    ("salt_g", r"salt", ()),
    ("protein_g", r"proteins?", ()),
    ("carbs_g", r"(?:total\s+)?carbohydrates?|carbs?", ()),
    ("fat_g", r"(?:total\s+)?fat", ("saturated ", "trans ", "sat. ", "sat ", "unsaturated ", "mono", "poly", "low ", "no ", "free ", "-")),
]


def _to_float(text):
    return float(text.replace(",", "."))


def _clean(text):
    text = text.replace("\r", "\n").replace("|", " ").replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", text)


def split_ingredients(text):
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    items, depth, current = [], 0, []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    items.append("".join(current))
    return [item.strip(" .:-") for item in items if item.strip(" .:-")]


def _cut_block(text, start):
    rest = text[start:]
    stop = STOP_LINE.search(rest, 1)
    inline = STOP_INLINE.search(rest)
    ends = [m.start() for m in (stop, inline) if m]
    return rest[:min(ends)] if ends else rest


def _guess_block(text):
    """No 'Ingredients' heading was read: use the longest run of comma-heavy lines."""
    best, run = "", []
    for line in text.splitlines() + [""]:
        looks = line.count(",") >= 2 and not re.search(r"\d+\s*(?:kcal|kj|mg)\b", line, re.I)
        if looks:
            run.append(line)
            continue
        if run and len(" ".join(run)) > len(best):
            best = " ".join(run)
        run = []
    return best if best.count(",") >= 3 else ""


def extract_ingredients_text(text):
    text = _clean(text)
    match = ING_HEAD_LINE.search(text) or ING_HEAD_INLINE.search(text)
    if match:
        block = _cut_block(text, match.end())
    else:
        block = _guess_block(text)
    block = re.sub(r"\s+", " ", block).strip(" :-.")
    return block


def extract_allergen_statements(text):
    contains = " ".join(m.group(1) for m in CONTAINS_RE.finditer(text))
    trace = " ".join(m.group(1) for m in MAY_CONTAIN_RE.finditer(text))
    return contains.strip(), trace.strip()


def _normalise_code(match):
    number, letter, roman = match.group(1), (match.group(2) or "").lower(), (match.group(3) or "").lower()
    if not letter and roman and number == "150":
        letter = ROMAN_150.get(roman, "")
    return "E" + number + letter


def extract_e_numbers(text):
    text = _clean(text or "")
    found = set()
    for m in E_NUMBER_RE.finditer(text):
        found.add("E" + m.group(1).lower())
    for regex in (PAREN_CODES_RE, CLASS_CODE_RE):
        for group in regex.finditer(text):
            for code in CODE_RE.finditer(group.group(1)):
                number = int(code.group(1))
                if 100 <= number <= 1599:
                    found.add(_normalise_code(code))
    return sorted(found)


def _nutrition_text(text, ingredients_text):
    if ingredients_text:
        text = text.replace(ingredients_text, " ")
        text = ING_HEAD_LINE.sub(" ", text)
    match = re.search(r"nutrition(?:al)?|nutrient|average\s+(?:values|composition)|typical\s+values", text, re.IGNORECASE)
    return text[match.start():] if match else text


def _find_value(section, key, pattern, forbid, serving_first):
    lowered = section.lower()
    for m in re.finditer(r"(?<![a-z])(?:" + pattern + r")(?![a-z])", lowered):
        before = lowered[max(0, m.start() - 12):m.start()]
        if any(before.endswith(word) or before.rstrip().endswith(word.strip()) for word in forbid if word.strip()):
            continue
        end = m.end()
        line_end = lowered.find("\n", end)
        segment = lowered[end:end + 70 if line_end == -1 else min(line_end, end + 70)]
        numbers = list(re.finditer(NUM + r"\s*" + UNIT + r"?(?![a-z])", segment))
        if not numbers:
            if re.search(r"\b(?:nil|not detected|trace|nd)\b", segment):
                return 0.0
            continue
        pick = numbers[1] if serving_first and len(numbers) > 1 else numbers[0]
        value = _to_float(pick.group(1))
        unit = (pick.group(2) or "").lower().replace("gm", "g").replace("μ", "µ")
        between = segment[:pick.start()]
        hint = re.search(r"\(\s*(kcal|kj|mg|mcg|µg|μg|g)\s*\)", between)
        at_line_start = lowered.rfind("\n", 0, m.start()) >= lowered.rfind("\n", 0, m.start()) and not lowered[lowered.rfind("\n", 0, m.start()) + 1:m.start()].strip(" -•*>")
        if not unit and hint:
            unit = hint.group(1).replace("μ", "µ")
        if not unit and not at_line_start:
            continue
        return value, unit
    return None


def parse_nutrients(text):
    text = _clean(text)
    section = _nutrition_text(text, extract_ingredients_text(text))
    lowered = section.lower()
    basis = "per_100g"
    per_100 = re.search(r"100\s*(?:g|ml)", lowered)
    per_serving = re.search(r"per\s+serv(?:ing|e)|serving\s+size", lowered)
    if per_serving and not per_100:
        basis = "per_serving"
    serving_first = False
    for header in lowered.splitlines():
        h100 = re.search(r"100\s*(?:g|ml)", header)
        hserv = re.search(r"per\s+serv(?:ing|e)", header)
        if h100 and hserv:
            serving_first = hserv.start() < h100.start()
            break

    nutrients = {}
    for key, pattern, forbid in NUTRIENT_RULES:
        found = _find_value(section, key, pattern, forbid, serving_first)
        if found is None:
            continue
        if isinstance(found, float):
            nutrients[key] = 0.0
            continue
        value, unit = found
        if key in ("sodium_mg",):
            if unit == "g":
                value *= 1000
        elif key == "salt_g":
            if unit == "mg":
                value /= 1000
        elif unit == "mg":
            value /= 1000
        elif unit == "µg" or unit == "mcg":
            value /= 1_000_000
        nutrients[key] = round(value, 3)

    kcal = re.search(NUM + r"\s*kcal", lowered)
    kj = re.search(NUM + r"\s*kj", lowered)
    if kcal:
        nutrients["energy_kcal"] = round(_to_float(kcal.group(1)), 1)
    elif kj:
        nutrients["energy_kcal"] = round(_to_float(kj.group(1)) / 4.184, 1)
    else:
        found = _find_value(section, "energy_kcal", r"energy|calories", (), serving_first)
        if found and not isinstance(found, float):
            value, unit = found
            nutrients["energy_kcal"] = round(value / 4.184 if unit == "kj" else value, 1)

    if "salt_g" in nutrients:
        salt = nutrients.pop("salt_g")
        nutrients.setdefault("sodium_mg", round(salt * 400, 1))
    return nutrients, basis


def is_liquid_label(text):
    return bool(re.search(r"per\s*100\s*ml|100\s*ml", text, re.IGNORECASE))


def parse_label(text):
    text = _clean(text)
    ingredients_text = extract_ingredients_text(text)
    contains, trace = extract_allergen_statements(text)
    nutrients, basis = parse_nutrients(text)
    return {
        "ingredients_text": ingredients_text,
        "ingredients": split_ingredients(ingredients_text) if ingredients_text else [],
        "contains_text": contains,
        "trace_text": trace,
        "e_numbers": extract_e_numbers(ingredients_text),
        "nutrients": nutrients,
        "basis": basis,
        "liquid": is_liquid_label(text),
    }
