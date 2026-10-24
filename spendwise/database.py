import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Project root = the folder that contains app.py
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("SPENDWISE_DB") or BASE_DIR / "data" / "spendwise.db")

DEFAULT_CATEGORIES = [
    ("Food & Dining", "expense"),
    ("Rent & Utilities", "expense"),
    ("Transport", "expense"),
    ("Shopping", "expense"),
    ("Health", "expense"),
    ("Entertainment", "expense"),
    ("Education", "expense"),
    ("Travel", "expense"),
    ("Other", "expense"),
    ("Salary", "income"),
    ("Freelance", "income"),
    ("Investments", "income"),
    ("Other Income", "income"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    UNIQUE (name, type)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    amount REAL NOT NULL CHECK (amount > 0),
    category_id INTEGER NOT NULL REFERENCES categories (id),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    month TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    UNIQUE (category_id, month)
);
"""


@contextmanager
def get_connection():
    """Open the database, save changes if all went well, undo them if not."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if missing and add default categories on first run."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO categories (name, type) VALUES (?, ?)",
                DEFAULT_CATEGORIES,
            )


def query(sql, params=()):
    """Run a SELECT and return the rows as a list of dictionaries."""
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]