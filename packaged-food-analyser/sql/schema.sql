PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS scans;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS ingredient_flags;
DROP TABLE IF EXISTS allergens;
DROP TABLE IF EXISTS additives;
DROP TABLE IF EXISTS nutrient_benchmarks;

CREATE TABLE nutrient_benchmarks (
    nutrient TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    unit TEXT NOT NULL,
    daily_value REAL NOT NULL CHECK (daily_value > 0),
    kind TEXT NOT NULL CHECK (kind IN ('limit', 'target')),
    max_penalty REAL NOT NULL DEFAULT 0,
    max_bonus REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL
);

CREATE TABLE additives (
    e_number TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    risk TEXT NOT NULL CHECK (risk IN ('low', 'moderate', 'high')),
    note TEXT NOT NULL
);

CREATE TABLE allergens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    keyword TEXT NOT NULL,
    UNIQUE (name, keyword)
);

CREATE TABLE ingredient_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL UNIQUE,
    flag TEXT NOT NULL CHECK (flag IN ('sugar', 'trans_fat_risk', 'palm_oil')),
    note TEXT NOT NULL
);

CREATE TABLE products (
    barcode TEXT PRIMARY KEY,
    name TEXT,
    brand TEXT,
    ingredients_text TEXT,
    nutrients_json TEXT,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT,
    input_type TEXT NOT NULL CHECK (input_type IN ('image', 'text', 'barcode')),
    score INTEGER NOT NULL,
    grade TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scans_created ON scans (created_at);
CREATE INDEX idx_allergens_name ON allergens (name);
