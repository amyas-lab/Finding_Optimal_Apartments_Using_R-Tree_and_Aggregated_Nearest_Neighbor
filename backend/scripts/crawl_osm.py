"""
Crawl amenity data from OpenStreetMap Overpass API for the Thu Duc / District 9
bounding box and insert into SQLite.

Run from the backend/ directory:
    python scripts/crawl_osm.py

Bounding box: (min_lat, min_lon, max_lat, max_lon) = (10.78, 106.70, 10.92, 106.85)
"""

import os
import sys
import time
import sqlite3
import urllib.request
import urllib.parse
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─────────────────────────────────────────────────────────────────────────────
#  Config — add a new amenity type here and everything else is automatic
# ─────────────────────────────────────────────────────────────────────────────

BBOX = "10.78,106.70,10.92,106.85"  # min_lat, min_lon, max_lat, max_lon

AMENITY_TYPES = [
    {
        "type_code": "hospital",
        "display_name": "Bệnh viện",
        "default_weight": 0.20,
        "osm_filter": 'node["amenity"="hospital"]; way["amenity"="hospital"];',
    },
    {
        "type_code": "pharmacy",
        "display_name": "Nhà thuốc",
        "default_weight": 0.10,
        "osm_filter": 'node["amenity"="pharmacy"]; way["amenity"="pharmacy"];',
    },
    {
        "type_code": "school",
        "display_name": "Trường học",
        "default_weight": 0.15,
        "osm_filter": 'node["amenity"="school"]; way["amenity"="school"];',
    },
    {
        "type_code": "university",
        "display_name": "Đại học",
        "default_weight": 0.10,
        "osm_filter": 'node["amenity"="university"]; way["amenity"="university"];',
    },
    {
        "type_code": "supermarket",
        "display_name": "Siêu thị",
        "default_weight": 0.15,
        "osm_filter": 'node["shop"="supermarket"]; way["shop"="supermarket"];',
    },
    {
        "type_code": "restaurant",
        "display_name": "Nhà hàng",
        "default_weight": 0.05,
        "osm_filter": 'node["amenity"="restaurant"]; way["amenity"="restaurant"];',
    },
    {
        "type_code": "park",
        "display_name": "Công viên",
        "default_weight": 0.10,
        "osm_filter": 'node["leisure"="park"]; way["leisure"="park"];',
    },
    {
        "type_code": "gym",
        "display_name": "Phòng gym",
        "default_weight": 0.05,
        "osm_filter": 'node["leisure"="fitness_centre"]; way["leisure"="fitness_centre"];',
    },
    {
        "type_code": "bus_stop",
        "display_name": "Bến xe buýt",
        "default_weight": 0.05,
        "osm_filter": 'node["highway"="bus_stop"];',
    },
    {
        "type_code": "highway",
        "display_name": "Đường cao tốc",
        "default_weight": 0.05,
        "osm_filter": 'node["highway"="motorway_junction"]; way["highway"="motorway"]; way["highway"="trunk"];',
    },
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DELAY_SECONDS = 1.5

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apartmentgps.db")

_dict_factory = lambda cur, row: {col[0]: row[idx] for idx, col in enumerate(cur.description)}


# ─────────────────────────────────────────────────────────────────────────────
#  Overpass query
# ─────────────────────────────────────────────────────────────────────────────

def build_query(osm_filter: str, bbox: str) -> str:
    """
    Build an Overpass QL query for the given filter and bounding box.
    Ways use 'out center' so we get a representative lat/lon.
    """
    lines = []
    for clause in osm_filter.split(";"):
        clause = clause.strip()
        if not clause:
            continue
        tag, _, rest = clause.partition("[")
        tag = tag.strip()
        filter_part = "[" + rest if rest else ""
        lines.append(f'  {tag}{filter_part}({bbox});')

    inner = "\n".join(lines)
    return (
        f"[out:json][timeout:60];\n"
        f"(\n{inner}\n);\n"
        f"out center;"
    )


def fetch_overpass(query: str) -> list:
    """POST query to Overpass API, return list of elements."""
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "ApartmentGPS/1.0 (educational project)"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())["elements"]


def extract_point(element: dict) -> tuple[float, float] | None:
    """Return (lat, lon) from a node or way element, or None if unavailable."""
    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        # way with out center
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


# ─────────────────────────────────────────────────────────────────────────────
#  Database helpers
# ─────────────────────────────────────────────────────────────────────────────

def init_schema(conn):
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


def sync_amenity_types(cur, conn) -> dict:
    """
    UPSERT amenity_types from AMENITY_TYPES list.
    Returns {type_code: id} mapping.
    """
    for t in AMENITY_TYPES:
        cur.execute(
            """
            INSERT OR REPLACE INTO amenity_types (type_code, display_name, default_weight)
            VALUES (?, ?, ?)
            """,
            (t["type_code"], t["display_name"], t["default_weight"]),
        )
    conn.commit()

    cur.execute("SELECT id, type_code FROM amenity_types")
    return {row["type_code"]: row["id"] for row in cur.fetchall()}


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def crawl():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    init_schema(conn)
    cur = conn.cursor()

    # 1. Sync amenity_types table
    print("Syncing amenity_types table…")
    type_id_map = sync_amenity_types(cur, conn)
    print(f"  → {len(type_id_map)} types in DB: {list(type_id_map.keys())}\n")

    # 2. Clear existing amenities
    print("Clearing amenities table…")
    cur.execute("DELETE FROM amenities")
    conn.commit()
    print("  → done\n")

    total_inserted = 0

    for t in AMENITY_TYPES:
        code = t["type_code"]
        type_id = type_id_map[code]
        query = build_query(t["osm_filter"], BBOX)

        print(f"Fetching {code} ({t['display_name']})…", end=" ", flush=True)
        try:
            elements = fetch_overpass(query)
        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(DELAY_SECONDS)
            continue

        rows = []
        for el in elements:
            point = extract_point(el)
            if point is None:
                continue
            lat, lon = point
            name = (
                el.get("tags", {}).get("name")
                or el.get("tags", {}).get("name:vi")
                or f"{t['display_name']} (unknown)"
            )
            rows.append((type_id, name, lat, lon))

        if rows:
            cur.executemany(
                "INSERT INTO amenities (type_id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
                rows,
            )
            conn.commit()

        print(f"{len(rows)} records inserted")
        total_inserted += len(rows)
        time.sleep(DELAY_SECONDS)

    cur.close()
    conn.close()

    print(f"\nDone. Total amenities inserted: {total_inserted}")

    # 3. Print final counts per type
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = _dict_factory
    cur2 = conn2.cursor()
    cur2.execute("""
        SELECT t.type_code, t.display_name, COUNT(a.id) AS count
        FROM amenity_types t
        LEFT JOIN amenities a ON a.type_id = t.id
        GROUP BY t.id
        ORDER BY t.id
    """)
    print("\nFinal counts:")
    print(f"  {'type_code':<15} {'display_name':<20} count")
    print("  " + "-" * 45)
    for row in cur2.fetchall():
        print(f"  {row['type_code']:<15} {row['display_name']:<20} {row['count']}")
    cur2.close()
    conn2.close()


if __name__ == "__main__":
    crawl()
