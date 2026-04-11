"""
Search endpoint integration test.

Calls the live FastAPI server at http://localhost:8000.
Make sure the server is running before executing this script:
    uvicorn main:app --reload --port 8000   (in another terminal)

Run from the backend/ directory:
    python scripts/test_search.py

Tests:
  1. GET  /amenity-types    → returns a non-empty list with required fields
  2. GET  /apartments       → returns a non-empty list with required fields
  3. POST /search           → returns top-k results, sorted by adist, with nearest_amenities
  4. POST /search           → single-type weight still works
  5. POST /search (edge)    → invalid body returns HTTP 422
"""

import sys
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

failures = 0


# ─────────────────────────────────────────────────────────────────────────────
#  Tiny HTTP helpers (stdlib only — no requests dependency needed)
# ─────────────────────────────────────────────────────────────────────────────

def get(path: str):
    url = BASE + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def post(path: str, body: dict):
    url = BASE + path
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(label: str, cond: bool, detail: str = ""):
    global failures
    status = PASS if cond else FAIL
    print(f"  {status}  {label}" + (f"  ← {detail}" if detail and not cond else ""))
    if not cond:
        failures += 1


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_amenity_types():
    print("\n── GET /amenity-types ──────────────────────────────────────────")
    status, data = get("/amenity-types")
    check("HTTP 200",                   status == 200, f"got {status}")
    check("returns a list",             isinstance(data, list))
    check("at least one type",          len(data) >= 1, f"got {len(data)}")
    if data:
        t = data[0]
        check("has type_code field",    "type_code"      in t)
        check("has display_name field", "display_name"   in t)
        check("has default_weight",     "default_weight" in t)
    print(f"  Found types: {[t['type_code'] for t in data]}")


def test_apartments():
    print("\n── GET /apartments ─────────────────────────────────────────────")
    status, data = get("/apartments")
    check("HTTP 200",                   status == 200,          f"got {status}")
    check("returns a list",             isinstance(data, list))
    check("at least one apartment",     len(data) >= 1,         f"got {len(data)}")
    if data:
        a = data[0]
        for field in ("id", "name", "address", "latitude", "longitude", "price_m2"):
            check(f"has '{field}' field", field in a)
    print(f"  Found {len(data)} apartments")


def test_search_multi_weight():
    print("\n── POST /search (multi-weight) ─────────────────────────────────")
    status, data = post("/search", {
        "weights": {"hospital": 0.5, "school": 0.3, "supermarket": 0.2},
        "top_k": 5,
    })
    check("HTTP 200",               status == 200,           f"got {status}")
    check("returns a list",         isinstance(data, list))
    check("at most 5 results",      len(data) <= 5,          f"got {len(data)}")
    check("at least 1 result",      len(data) >= 1)

    if len(data) >= 2:
        check("sorted by adist asc",
              data[0]["adist"] <= data[1]["adist"],
              f"{data[0]['adist']} > {data[1]['adist']}")

    if data:
        top = data[0]
        check("has adist",              "adist"             in top)
        check("has nearest_amenities",  "nearest_amenities" in top)
        na = top.get("nearest_amenities", {})
        check("nearest_amenities non-empty", len(na) >= 1)
        # Each entry should have name and distance_m
        for tc, info in na.items():
            check(f"  {tc} has distance_m", "distance_m" in info)

    print(f"\n  Top-5 results:")
    for i, apt in enumerate(data, 1):
        na_summary = ", ".join(
            f"{tc}={v['distance_m']}m" for tc, v in apt.get("nearest_amenities", {}).items()
        )
        print(f"    {i}. {apt['name'][:35]:35s}  adist={apt['adist']:8.1f} m  [{na_summary}]")


def test_search_single_weight():
    print("\n── POST /search (single type) ──────────────────────────────────")
    status, data = post("/search", {
        "weights": {"hospital": 1.0},
        "top_k": 3,
    })
    check("HTTP 200",        status == 200,  f"got {status}")
    check("returns list",    isinstance(data, list))
    check("≤ 3 results",     len(data) <= 3, f"got {len(data)}")

    if len(data) >= 2:
        check("sorted ascending", data[0]["adist"] <= data[1]["adist"])

    if data:
        na = data[0].get("nearest_amenities", {})
        check("only hospital in nearest_amenities", list(na.keys()) == ["hospital"],
              f"got {list(na.keys())}")
    print(f"  Nearest to hospitals: {[a['name'] for a in data]}")


def test_invalid_body():
    print("\n── POST /search (invalid body → 422) ───────────────────────────")
    # Empty weights
    status, _ = post("/search", {"weights": {}, "top_k": 5})
    check("empty weights → 422", status == 422, f"got {status}")

    # Negative weight
    status, _ = post("/search", {"weights": {"hospital": -1}, "top_k": 5})
    check("negative weight → 422", status == 422, f"got {status}")

    # top_k out of range
    status, _ = post("/search", {"weights": {"hospital": 1}, "top_k": 0})
    check("top_k=0 → 422", status == 422, f"got {status}")


# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"Testing API at {BASE}")
    print("(Make sure 'uvicorn main:app --port 8000' is running)\n")

    # Quick connectivity check
    try:
        get("/amenity-types")
    except Exception as e:
        print(f"\n\033[91mCannot reach {BASE} — is the server running?\033[0m")
        print(f"Error: {e}")
        sys.exit(1)

    test_amenity_types()
    test_apartments()
    test_search_multi_weight()
    test_search_single_weight()
    test_invalid_body()

    print("\n" + "─" * 60)
    if failures == 0:
        print("ALL TESTS PASSED ✓")
        sys.exit(0)
    else:
        print(f"{failures} TEST(S) FAILED ✗")
        sys.exit(1)


if __name__ == "__main__":
    main()
