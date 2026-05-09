"""
Database layer — SQLite connection and query helpers.
Database file: backend/apartmentgps.db (auto-created on first use).
"""

import os
import sqlite3
from typing import Dict, List

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apartmentgps.db")

_dict_factory = lambda cur, row: {col[0]: row[idx] for idx, col in enumerate(cur.description)}


def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = _dict_factory
    _init_schema(conn)
    return conn


def _init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS apartments (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            address     TEXT,
            latitude    REAL NOT NULL,
            longitude   REAL NOT NULL,
            price_m2    REAL
        );
        CREATE TABLE IF NOT EXISTS amenity_types (
            id              INTEGER PRIMARY KEY,
            type_code       TEXT NOT NULL UNIQUE,
            display_name    TEXT,
            default_weight  REAL
        );
        CREATE TABLE IF NOT EXISTS amenities (
            id          INTEGER PRIMARY KEY,
            type_id     INTEGER NOT NULL,
            name        TEXT,
            latitude    REAL NOT NULL,
            longitude   REAL NOT NULL,
            FOREIGN KEY (type_id) REFERENCES amenity_types(id)
        );
    """)


# ─────────────────────────────────────────────────────────────────────────────

def load_apartments() -> List[dict]:
    """Return all rows from the `apartments` table as plain dicts."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, address, latitude, longitude, price_m2 FROM apartments"
        )
        rows = cur.fetchall()
        for row in rows:
            row["latitude"] = float(row["latitude"])
            row["longitude"] = float(row["longitude"])
            if row["price_m2"] is not None:
                row["price_m2"] = float(row["price_m2"])
        return rows
    finally:
        conn.close()


def load_amenities_by_type() -> Dict[str, List[dict]]:
    """
    Return amenities grouped by type_code.

    Structure: {type_code: [{id, name, latitude, longitude, type_code, display_name}, …]}
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.name,
                a.latitude,
                a.longitude,
                t.type_code,
                t.display_name
            FROM amenities a
            JOIN amenity_types t ON a.type_id = t.id
            """
        )
        rows = cur.fetchall()
        result: Dict[str, List[dict]] = {}
        for row in rows:
            row["latitude"] = float(row["latitude"])
            row["longitude"] = float(row["longitude"])
            result.setdefault(row["type_code"], []).append(row)
        return result
    finally:
        conn.close()


def load_amenity_types() -> List[dict]:
    """Return all rows from `amenity_types`."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, type_code, display_name, default_weight FROM amenity_types"
        )
        rows = cur.fetchall()
        for row in rows:
            if row["default_weight"] is not None:
                row["default_weight"] = float(row["default_weight"])
        return rows
    finally:
        conn.close()
