ABOUT = {
    "institute": "Don Bosco Institute of Technology, Kurla, Mumbai",
    "course": "First-year Computer Engineering",
    "stack": ["Python", "Flask", "SQLite", "Tesseract OCR", "HTML, CSS and JavaScript"],
}

# Keep in step with the ingredient checks in app/analysis.py (analyze()).
INGREDIENT_RULES = [
    ("Sugar as first, second or third ingredient", "8 to 15"),
    ("Three or more different sugar names", 3),
    ("Hydrogenated or vanaspati-type fat", 5),
    ("Palm oil", 2),
    ("Flavours, colours, sweeteners and other processing markers (2 each)", "up to 10"),
    ("E-number missing from our table (2 each, counted with additives)", 2),
    ("Sugary or sweetened drink: score ceiling", "grade E to C"),
    ("No nutrition table read: score ceiling", "55"),
]

# Fill in "name" for each member. An empty name is simply not shown.
TEAM = [
    {
        "name": "",
        "role": "Scoring engine",
        "work": "Turns ingredients and nutrition values into the 0 to 100 score, the A to E grade and the plain-language summary.",
    },
    {
        "name": "",
        "role": "Label reading",
        "work": "Photo cleanup, Tesseract OCR, barcode decoding, and parsing ingredient lists and nutrition tables, including per-serving labels.",
    },
    {
        "name": "",
        "role": "Data and database",
        "work": "The SQLite schema, additive, allergen and WHO reference data, product lookup, the Open Food Facts importer and the survey.",
    },
    {
        "name": "",
        "role": "Interface and testing",
        "work": "Every page you are looking at, the report and compare views, the test suite and the documentation.",
    },
]
