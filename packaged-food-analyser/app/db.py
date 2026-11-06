import sqlite3
from pathlib import Path

from flask import current_app, g

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    for name in ("schema.sql", "seed.sql"):
        conn.executescript((SQL_DIR / name).read_text(encoding="utf-8"))
    conn.commit()
    from .reference_extra import ensure_reference
    ensure_reference(conn)
    conn.close()
