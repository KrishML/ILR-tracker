"""
SQLite persistence layer for ILR Absence Tracker.

Schema
------
trips
  id          INTEGER PRIMARY KEY AUTOINCREMENT
  destination TEXT    NOT NULL
  date_out    TEXT    NOT NULL  -- ISO-8601 YYYY-MM-DD
  date_in     TEXT    NOT NULL  -- ISO-8601 YYYY-MM-DD
  source      TEXT    NOT NULL  -- 'excel' | 'manual'
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "ilr_tracker.db")


# ── Connection helper ─────────────────────────────────────────────────────────
@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── Schema init ───────────────────────────────────────────────────────────────
def init_db() -> None:
    """Create the trips table if it doesn't exist."""
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                destination TEXT    NOT NULL,
                date_out    TEXT    NOT NULL,
                date_in     TEXT    NOT NULL,
                source      TEXT    NOT NULL DEFAULT 'manual'
            )
        """)
        # Unique constraint to prevent duplicate seeding from Excel
        con.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_trip
            ON trips (date_out, date_in, source)
        """)


# ── Seeding ───────────────────────────────────────────────────────────────────
def seed_excel_trips(trips: list[tuple[str, str, str]]) -> int:
    """
    Insert Excel trips that don't already exist.
    Each item is (destination, date_out, date_in).
    Returns the number of newly inserted rows.
    """
    inserted = 0
    with _conn() as con:
        for dest, date_out, date_in in trips:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO trips (destination, date_out, date_in, source)
                VALUES (?, ?, ?, 'excel')
                """,
                (dest, date_out, date_in),
            )
            inserted += cur.rowcount
    return inserted


# ── Reads ─────────────────────────────────────────────────────────────────────
def get_all_trips() -> list[dict]:
    """Return all trips ordered by date_out."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, destination, date_out, date_in, source FROM trips ORDER BY date_out"
        ).fetchall()
    return [dict(r) for r in rows]


def get_manual_trips() -> list[dict]:
    """Return only manually added trips ordered by date_out."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, destination, date_out, date_in, source FROM trips "
            "WHERE source = 'manual' ORDER BY date_out"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Writes ────────────────────────────────────────────────────────────────────
def add_trip(destination: str, date_out: str, date_in: str) -> int:
    """Insert a manual trip and return its new id."""
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO trips (destination, date_out, date_in, source) VALUES (?, ?, ?, 'manual')",
            (destination, date_out, date_in),
        )
    return cur.lastrowid


def update_trip(trip_id: int, destination: str, date_out: str, date_in: str) -> None:
    """Update destination and dates for a manual trip."""
    with _conn() as con:
        con.execute(
            "UPDATE trips SET destination = ?, date_out = ?, date_in = ? WHERE id = ? AND source = 'manual'",
            (destination, date_out, date_in, trip_id),
        )


def delete_trip(trip_id: int) -> None:
    """Delete a manual trip by id."""
    with _conn() as con:
        con.execute("DELETE FROM trips WHERE id = ? AND source = 'manual'", (trip_id,))
