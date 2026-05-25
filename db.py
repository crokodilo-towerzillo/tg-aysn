import os
import sqlite3
from datetime import datetime, timezone

import config

DB_PATH = os.getenv("DB_PATH", "aysn.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id             INTEGER PRIMARY KEY,
                user_id        INTEGER NOT NULL,
                label          TEXT    NOT NULL,
                key_enc        BLOB    NOT NULL,
                last_synced_at TEXT,
                is_valid       INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS reports (
                id                INTEGER PRIMARY KEY,
                key_id            INTEGER NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
                report_id         INTEGER NOT NULL,
                date_from         TEXT    NOT NULL,
                date_to           TEXT    NOT NULL,
                report_type       INTEGER NOT NULL,
                retail_amount_sum REAL    NOT NULL,
                UNIQUE(key_id, report_id)
            );
            CREATE TABLE IF NOT EXISTS fsm_state (
                key   TEXT PRIMARY KEY,
                state TEXT,
                data  TEXT
            );
        """)


def add_key(user_id: int, label: str, api_key: str) -> int:
    key_enc = config.fernet.encrypt(api_key.encode())
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO api_keys (user_id, label, key_enc) VALUES (?, ?, ?)",
            (user_id, label, key_enc),
        )
        return cur.lastrowid


def get_keys(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM api_keys WHERE user_id = ?", (user_id,)
        ).fetchall()


def get_key(key_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()


def decrypt_key(row: sqlite3.Row) -> str:
    return config.fernet.decrypt(bytes(row["key_enc"])).decode()


def delete_key(key_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))


def update_last_synced(key_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE api_keys SET last_synced_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), key_id),
        )


def update_key_validity(key_id: int, is_valid: bool):
    with get_conn() as conn:
        conn.execute(
            "UPDATE api_keys SET is_valid = ? WHERE id = ?",
            (1 if is_valid else 0, key_id),
        )


def upsert_report(
    key_id: int,
    report_id: int,
    date_from: str,
    date_to: str,
    report_type: int,
    retail_amount_sum: float,
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO reports
                (key_id, report_id, date_from, date_to, report_type, retail_amount_sum)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key_id, report_id) DO UPDATE SET
                retail_amount_sum = excluded.retail_amount_sum
            """,
            (key_id, report_id, date_from, date_to, report_type, retail_amount_sum),
        )


def fsm_set_state(key: str, state: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO fsm_state(key, state) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET state=excluded.state",
            (key, state),
        )


def fsm_get_state(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM fsm_state WHERE key=?", (key,)).fetchone()
        return row["state"] if row else None


def fsm_set_data(key: str, data_json: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO fsm_state(key, data) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET data=excluded.data",
            (key, data_json),
        )


def fsm_get_data(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT data FROM fsm_state WHERE key=?", (key,)).fetchone()
        return row["data"] if row else None


def get_reports_for_period(
    key_id: int,
    month_from: tuple[int, int],
    month_to: tuple[int, int],
) -> list[sqlite3.Row]:
    ym_from = f"{month_from[0]:04d}-{month_from[1]:02d}"
    ym_to = f"{month_to[0]:04d}-{month_to[1]:02d}"
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM reports
            WHERE key_id = ?
              AND strftime('%Y-%m', date_to) >= ?
              AND strftime('%Y-%m', date_to) <= ?
            """,
            (key_id, ym_from, ym_to),
        ).fetchall()
