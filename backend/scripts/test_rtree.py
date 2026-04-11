"""
R-tree build verification script.

Run from the backend/ directory:
    python scripts/test_rtree.py

Checks:
  1. Loads amenities from the database.
  2. Builds one R-tree per amenity type using STR.
  3. Verifies tree structure (MBR containment, leaf entry count).
  4. Runs a NN query for a known point and prints the result.
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import load_amenities_by_type
from rtree.build import str_build
from rtree.node import RTreeNode, haversine
from rtree.search import nearest_neighbor

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


# ─────────────────────────────────────────────────────────────────────────────
#  Helper — walk the tree and collect stats
# ─────────────────────────────────────────────────────────────────────────────

def tree_stats(node: RTreeNode, depth: int = 0) -> dict:
    """Recursively compute height, node count, and total leaf entries."""
    if node.is_leaf:
        return {"height": depth, "nodes": 1, "entries": len(node.entries)}
    child_stats = [tree_stats(c, depth + 1) for c in node.children]
    return {
        "height":  max(s["height"]  for s in child_stats),
        "nodes":   1 + sum(s["nodes"]   for s in child_stats),
        "entries": sum(s["entries"] for s in child_stats),
    }


def verify_mbr_containment(node: RTreeNode, parent_mbr=None) -> list[str]:
    """Return a list of violation messages (empty = all good)."""
    errors = []
    if parent_mbr is not None:
        eps = 1e-9
        if (node.mbr.min_lat < parent_mbr.min_lat - eps or
                node.mbr.min_lon < parent_mbr.min_lon - eps or
                node.mbr.max_lat > parent_mbr.max_lat + eps or
                node.mbr.max_lon > parent_mbr.max_lon + eps):
            errors.append(
                f"MBR containment violated: child {node.mbr} not inside parent {parent_mbr}"
            )
    if node.is_leaf:
        for e in node.entries:
            if not (node.mbr.min_lat - 1e-9 <= e["latitude"]  <= node.mbr.max_lat + 1e-9 and
                    node.mbr.min_lon - 1e-9 <= e["longitude"] <= node.mbr.max_lon + 1e-9):
                errors.append(
                    f"Entry ({e['latitude']}, {e['longitude']}) outside leaf MBR {node.mbr}"
                )
    else:
        for child in node.children:
            errors.extend(verify_mbr_containment(child, node.mbr))
    return errors


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_build_and_structure():
    print("\n── Test 1: build R-trees from DB ──────────────────────────────")
    by_type = load_amenities_by_type()
    assert by_type, "No amenities found — did you run scripts/seed.py first?"

    all_passed = True
    trees = {}
    for type_code, entries in by_type.items():
        tree = str_build(entries)
        trees[type_code] = tree
        stats = tree_stats(tree)
        errors = verify_mbr_containment(tree)
        ok = len(errors) == 0 and stats["entries"] == len(entries)
        status = PASS if ok else FAIL
        if not ok:
            all_passed = False
        print(
            f"  {status}  {type_code:12s}  "
            f"{len(entries):3d} entries  "
            f"height={stats['height']}  nodes={stats['nodes']}  "
            + ("" if ok else f"ERRORS: {errors[:2]}")
        )

    print(f"\n  Result: {'ALL PASSED' if all_passed else 'SOME FAILURES'}")
    return trees, all_passed


def test_nn_correctness(trees, by_type):
    print("\n── Test 2: nearest-neighbour correctness ───────────────────────")
    # Query point: Vinhomes Grand Park main gate area
    q_lat, q_lon = 10.8460, 106.7760
    print(f"  Query point: ({q_lat}, {q_lon})  [Vinhomes Grand Park area]")

    all_passed = True
    for type_code, tree in trees.items():
        entries = by_type[type_code]

        # Brute-force ground truth
        bf_best = min(entries, key=lambda e: haversine(q_lat, q_lon, e["latitude"], e["longitude"]))
        bf_dist = haversine(q_lat, q_lon, bf_best["latitude"], bf_best["longitude"])

        # R-tree result
        nn = nearest_neighbor(tree, q_lat, q_lon)
        nn_dist = haversine(q_lat, q_lon, nn["latitude"], nn["longitude"])

        ok = abs(nn_dist - bf_dist) < 0.01   # within 1 cm — should be exact
        status = PASS if ok else FAIL
        if not ok:
            all_passed = False
        print(
            f"  {status}  {type_code:12s}  "
            f"NN='{nn['name']}'  dist={nn_dist:.1f} m  "
            f"brute-force='{bf_best['name']}'  dist={bf_dist:.1f} m"
            + ("" if ok else "  ← MISMATCH")
        )

    print(f"\n  Result: {'ALL PASSED' if all_passed else 'SOME FAILURES'}")
    return all_passed


def test_edge_cases():
    print("\n── Test 3: edge cases ──────────────────────────────────────────")

    # Empty tree
    tree = str_build([])
    ok1 = tree is None
    print(f"  {PASS if ok1 else FAIL}  str_build([]) returns None: {ok1}")

    # Single entry
    single = [{"latitude": 10.845, "longitude": 106.776, "name": "X", "id": 99}]
    tree = str_build(single)
    nn = nearest_neighbor(tree, 10.845, 106.776)
    ok2 = nn is not None and nn["id"] == 99
    print(f"  {PASS if ok2 else FAIL}  single-entry tree NN returns correct entry: {ok2}")

    # Query point inside MBR
    nn_inside = nearest_neighbor(tree, 10.844, 106.775)
    ok3 = nn_inside is not None
    print(f"  {PASS if ok3 else FAIL}  NN from point near entry still returns result: {ok3}")

    return ok1 and ok2 and ok3


# ─────────────────────────────────────────────────────────────────────────────

def main():
    trees, ok1 = test_build_and_structure()
    by_type = load_amenities_by_type()
    ok2 = test_nn_correctness(trees, by_type)
    ok3 = test_edge_cases()

    print("\n" + "─" * 60)
    overall = ok1 and ok2 and ok3
    print(f"Overall: {'ALL TESTS PASSED ✓' if overall else 'SOME TESTS FAILED ✗'}")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
