
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import bcrypt

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT UNIQUE NOT NULL,
    hashed_password BLOB NOT NULL,
    full_name       TEXT NOT NULL,
    cash_balance    REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS holdings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker        TEXT NOT NULL,
    name          TEXT NOT NULL,
    asset_class   TEXT NOT NULL,
    qty           REAL NOT NULL,
    target_weight REAL NOT NULL,
    UNIQUE(user_id, ticker)
);
"""

# (ticker, name, asset_class, qty, target_weight)
DEMO_HOLDINGS = [
    ("AAPL",    "Apple Inc.",         "Equity - Tech",       120, 0.18),
    ("MSFT",    "Microsoft Corp.",    "Equity - Tech",       80,  0.16),
    ("GOOGL",   "Alphabet Inc.",      "Equity - Tech",       60,  0.12),
    ("AMZN",    "Amazon.com Inc.",    "Equity - Consumer",   70,  0.10),
    ("NVDA",    "NVIDIA Corp.",       "Equity - Tech",       90,  0.14),
    ("TSLA",    "Tesla Inc.",         "Equity - Auto",       50,  0.08),
    ("JPM",     "JPMorgan Chase",     "Equity - Financials", 100, 0.10),
    ("BTC-USD", "Bitcoin",            "Cryptocurrency",      0.5, 0.08),
    ("ETH-USD", "Ethereum",           "Cryptocurrency",      5,   0.04),
]
DEMO_EMAIL = "demo@portfolio.io"
DEMO_PASSWORD = "Demo@1234"
DEMO_CASH_BALANCE = 42_110.0

_init_lock = threading.Lock()
_initialized = False


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:

    global _initialized
    with _init_lock:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with get_conn() as conn:
            conn.executescript(SCHEMA)
            _seed_demo_user(conn)
        _initialized = True


def _seed_demo_user(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    if row is not None:
        return  # already seeded

    hashed = bcrypt.hashpw(DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt())
    cur = conn.execute(
        "INSERT INTO users (email, hashed_password, full_name, cash_balance) VALUES (?, ?, ?, ?)",
        (DEMO_EMAIL, hashed, "Demo Manager", DEMO_CASH_BALANCE),
    )
    user_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO holdings (user_id, ticker, name, asset_class, qty, target_weight) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(user_id, *row) for row in DEMO_HOLDINGS],
    )


def _ensure_initialized() -> None:
    if not _initialized:
        init_db()


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    _ensure_initialized()
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_demo_user_id() -> int:
    """The app is still single-tenant end-to-end (one demo login) — this is
    the one seam other modules use to ask 'whose portfolio is this'. When
    real multi-user auth is added later, swap this for the authenticated
    user's id."""
    user = get_user_by_email(DEMO_EMAIL)
    if user is None:
        raise RuntimeError("Demo user not found — did init_db() run?")
    return user["id"]

def get_holdings(user_id: int) -> list[sqlite3.Row]:
    _ensure_initialized()
    with get_conn() as conn:
        return conn.execute(
            "SELECT ticker, name, asset_class, qty, target_weight "
            "FROM holdings WHERE user_id = ? ORDER BY ticker", (user_id,)
        ).fetchall()


def get_cash_balance(user_id: int) -> float:
    _ensure_initialized()
    with get_conn() as conn:
        row = conn.execute("SELECT cash_balance FROM users WHERE id = ?", (user_id,)).fetchone()
        return float(row["cash_balance"]) if row else 0.0


def set_cash_balance(user_id: int, amount: float) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET cash_balance = ? WHERE id = ?", (amount, user_id))


def upsert_holding(user_id: int, ticker: str, name: str, asset_class: str,
                    qty: float, target_weight: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO holdings (user_id, ticker, name, asset_class, qty, target_weight)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, ticker) DO UPDATE SET
                 name=excluded.name, asset_class=excluded.asset_class,
                 qty=excluded.qty, target_weight=excluded.target_weight""",
            (user_id, ticker, name, asset_class, qty, target_weight),
        )


def delete_holding(user_id: int, ticker: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM holdings WHERE user_id = ? AND ticker = ?", (user_id, ticker))


def reset_demo_holdings() -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
        if row is None:
            raise RuntimeError("Demo user not found — run init_db() first.")
        user_id = row["id"]
        conn.execute("DELETE FROM holdings WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO holdings (user_id, ticker, name, asset_class, qty, target_weight) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(user_id, *r) for r in DEMO_HOLDINGS],
        )
    print(f"Demo holdings reset to: {', '.join(t for t, *_ in DEMO_HOLDINGS)}")

init_db()