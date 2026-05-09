"""
Seed script — insert sample apartments and amenities into ApartmentGPS.

Run from the backend/ directory:
    python scripts/seed.py

All coordinates are real locations inside District 9 (Thủ Đức City), HCMC.
The script is idempotent: it clears existing rows before inserting so you
can run it multiple times safely.
"""

import sys
import os
import sqlite3

# Make sure the backend package root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apartmentgps.db")

# ─────────────────────────────────────────────────────────────────────────────
#  Sample data
# ─────────────────────────────────────────────────────────────────────────────

AMENITY_TYPES = [
    # (type_code, display_name, default_weight)
    ("hospital",    "Hospital",    0.35),
    ("school",      "School",      0.30),
    ("supermarket", "Supermarket", 0.20),
    ("park",        "Park",        0.15),
]

APARTMENTS = [
    # (name, address, latitude, longitude, price_m2)
    ("Vinhomes Grand Park - S1.01", "Vinhomes Grand Park, P. Long Bình, Thủ Đức",  10.8470, 106.7745, 45_000_000),
    ("Vinhomes Grand Park - S2.05", "Vinhomes Grand Park, P. Long Bình, Thủ Đức",  10.8450, 106.7770, 46_500_000),
    ("The Sun Avenue",              "28 Mai Chí Thọ, P. An Phú, Thủ Đức",          10.7915, 106.7515, 58_000_000),
    ("Masteri Thảo Điền",           "159 Xa Lộ Hà Nội, Thảo Điền, Thủ Đức",        10.8018, 106.7341, 72_000_000),
    ("Khang Điền Merita",           "Đường Liên Phường, P. Phú Hữu, Thủ Đức",      10.8264, 106.7881, 38_000_000),
    ("Eco Xuân",                    "Bình Dương, giáp ranh Q9",                     10.9012, 106.7534, 30_000_000),
    ("Q7 Saigon Riverside",         "P. Phú Thuận, Quận 7",                         10.7302, 106.7208, 55_000_000),
    ("Celadon City",                "Tân Phú",                                      10.7923, 106.6283, 42_000_000),
]

# {type_code: [(name, latitude, longitude), ...]}
AMENITIES = {
    "hospital": [
        ("Bệnh viện Quận 9",              10.8300, 106.7780),
        ("Bệnh viện Ung Bướu (cơ sở 2)", 10.8645, 106.7760),
        ("Phòng khám đa khoa An Sinh",    10.7900, 106.7450),
        ("Bệnh viện FV",                  10.7385, 106.7186),
        ("Trung tâm y tế Thủ Đức",        10.8500, 106.7600),
    ],
    "school": [
        ("THPT Long Trường",              10.8400, 106.7820),
        ("THCS Nguyễn Văn Bá",            10.8200, 106.7700),
        ("Trường Quốc tế Việt Úc Q9",     10.8350, 106.7610),
        ("Trường TH Trần Thị Bưởi",       10.7950, 106.7380),
        ("THPT Marie Curie",              10.7750, 106.7050),
        ("Trường Quốc tế BIS",            10.8020, 106.7340),
    ],
    "supermarket": [
        ("VinMart Vinhomes Grand Park",   10.8460, 106.7760),
        ("Co.opmart Phước Long",          10.8150, 106.7600),
        ("Lotte Mart Thủ Đức",            10.8480, 106.7520),
        ("Big C An Lạc",                  10.7590, 106.6140),
        ("Emart Gò Vấp",                  10.8380, 106.6710),
    ],
    "park": [
        ("Công viên Vinhomes Grand Park", 10.8455, 106.7755),
        ("Công viên Lịch sử Văn hóa DT", 10.8220, 106.7830),
        ("Công viên Long Bình",           10.8390, 106.7900),
        ("Công viên Bờ sông Sài Gòn",    10.7880, 106.7290),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  Insert logic
# ─────────────────────────────────────────────────────────────────────────────

def seed():
    conn = sqlite3.connect(DB_PATH)

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

    cur = conn.cursor()

    print("Clearing existing data…")
    cur.execute("DELETE FROM amenities")
    cur.execute("DELETE FROM amenity_types")
    cur.execute("DELETE FROM apartments")
    conn.commit()

    # amenity_types
    print("Inserting amenity types…")
    type_id_map = {}
    for type_code, display_name, default_weight in AMENITY_TYPES:
        cur.execute(
            "INSERT INTO amenity_types (type_code, display_name, default_weight) VALUES (?, ?, ?)",
            (type_code, display_name, default_weight),
        )
        type_id_map[type_code] = cur.lastrowid
    conn.commit()
    print(f"  → inserted {len(AMENITY_TYPES)} amenity types: {list(type_id_map.keys())}")

    # apartments
    print("Inserting apartments…")
    cur.executemany(
        "INSERT INTO apartments (name, address, latitude, longitude, price_m2) VALUES (?, ?, ?, ?, ?)",
        APARTMENTS,
    )
    conn.commit()
    print(f"  → inserted {len(APARTMENTS)} apartments")

    # amenities
    print("Inserting amenities…")
    rows = []
    for type_code, places in AMENITIES.items():
        tid = type_id_map[type_code]
        for name, lat, lon in places:
            rows.append((tid, name, lat, lon))
    cur.executemany(
        "INSERT INTO amenities (type_id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    print(f"  → inserted {len(rows)} amenities across {len(AMENITIES)} types")

    cur.close()
    conn.close()
    print("\nDone. Database is ready for testing.")


if __name__ == "__main__":
    seed()
