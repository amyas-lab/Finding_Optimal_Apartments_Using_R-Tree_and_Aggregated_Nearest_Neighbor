"""
Database layer — MySQL connection and query helpers.

Configuration is read from environment variables (see .env.example).
Connection pooling is left to the caller; each function opens and closes
its own connection so this module works correctly at startup and after a
/reload call.
"""

import os
from typing import Dict, List

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

_DB_CONFIG: dict = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3307")),
    "database": os.getenv("DB_NAME", "ApartmentGPS"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "cps0107"),
    "charset": "utf8mb4",
}


def _connect():
    return mysql.connector.connect(**_DB_CONFIG)


# ─────────────────────────────────────────────────────────────────────────────

def load_apartments() -> List[dict]:
    """Return all rows from the `apartments` table as plain dicts."""
    conn = _connect()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, name, address, latitude, longitude, price_m2 FROM apartments"
        )
        rows = cur.fetchall()
        # mysql-connector may return Decimal — cast to float for JSON serialisation
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
        cur = conn.cursor(dictionary=True)
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
        cur = conn.cursor(dictionary=True)
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
