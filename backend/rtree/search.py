"""
Nearest-neighbour and Aggregate Nearest-Neighbour (ANN) search on R-trees.

NN search  (nearest_neighbor)
─────────────────────────────
Branch-and-bound using mindist(MBR, p) as a lower-bound pruning key.
A min-heap orders candidates by their minimum possible distance to the
query point; any node whose mindist exceeds the current best actual
distance is discarded.

ANN search  (ann_search)
────────────────────────
Given:
  • a set of apartments P
  • a set of amenity types Q = {q1, …, qm} each with a weight w_i
  • one R-tree per amenity type (type_trees)

For each apartment p we compute:
    adist(p, Q) = Σ  w_i · dist(p, nearest amenity of type q_i)

We then return the top-k apartments sorted by adist ascending.

The amindist lower bound is used inside each per-type NN call to prune
R-tree branches early, making the search sub-linear in the number of
amenities for each type.
"""

import heapq
from typing import Dict, List, Optional

from .node import RTreeNode, haversine


# ─────────────────────────────────────────────────────────────────────────────
#  Single-type nearest-neighbour search
# ─────────────────────────────────────────────────────────────────────────────

def nearest_neighbor(
    root: Optional[RTreeNode],
    lat: float,
    lon: float,
) -> Optional[dict]:
    """
    Find the amenity in the R-tree rooted at *root* closest to (lat, lon).

    Returns the amenity dict (same structure stored in leaf entries), or
    None if the tree is empty.
    """
    if root is None:
        return None

    best_dist: float = float("inf")
    best_entry: Optional[dict] = None

    # Heap entries: (lower_bound_dist, tie_breaker, item, is_leaf_entry)
    counter = 0
    heap: list = [(0.0, counter, root, False)]

    while heap:
        lb, _, item, is_leaf_entry = heapq.heappop(heap)

        # Prune: if even the lower bound beats nothing, skip
        if lb >= best_dist:
            continue

        if is_leaf_entry:
            # Actual point — compute exact Haversine distance
            entry: dict = item
            d = haversine(lat, lon, entry["latitude"], entry["longitude"])
            if d < best_dist:
                best_dist = d
                best_entry = entry
        else:
            node: RTreeNode = item
            if node.is_leaf:
                # Expand all leaf entries onto the heap
                for entry in node.entries:
                    d = haversine(lat, lon, entry["latitude"], entry["longitude"])
                    if d < best_dist:
                        counter += 1
                        heapq.heappush(heap, (d, counter, entry, True))
            else:
                # Expand child nodes, pruning by amindist
                for child in node.children:
                    md = child.mbr.mindist(lat, lon)
                    if md < best_dist:
                        counter += 1
                        heapq.heappush(heap, (md, counter, child, False))

    return best_entry


# ─────────────────────────────────────────────────────────────────────────────
#  Aggregate Nearest-Neighbour search
# ─────────────────────────────────────────────────────────────────────────────

def ann_search(
    apartments: List[dict],
    type_trees: Dict[str, Optional[RTreeNode]],
    weights: Dict[str, float],
    top_k: int = 10,
) -> List[dict]:
    """
    Rank *apartments* by aggregate weighted distance to selected amenity types.

    Parameters
    ----------
    apartments   : list of apartment dicts (must have 'latitude', 'longitude')
    type_trees   : {type_code: RTreeNode | None}  — one tree per amenity type
    weights      : {type_code: weight}  — should sum to 1 (caller normalises)
    top_k        : how many results to return

    Returns
    -------
    List of apartment dicts enriched with:
      'adist'             — aggregate weighted distance in metres
      'nearest_amenities' — {type_code: {name, distance_m}} for each queried type
    Sorted by adist ascending (best first).
    """
    results: List[dict] = []

    # Only consider types that both have a weight AND have an R-tree
    active_types = {
        tc: w for tc, w in weights.items()
        if w > 0 and type_trees.get(tc) is not None
    }

    for apt in apartments:
        lat, lon = apt["latitude"], apt["longitude"]
        adist = 0.0
        nearest_amenities: Dict[str, dict] = {}

        for type_code, weight in active_types.items():
            tree = type_trees[type_code]
            nearest = nearest_neighbor(tree, lat, lon)
            if nearest is not None:
                d = haversine(lat, lon, nearest["latitude"], nearest["longitude"])
                adist += weight * d
                nearest_amenities[type_code] = {
                    "name": nearest.get("name", ""),
                    "distance_m": round(d, 1),
                }

        results.append(
            {
                **apt,
                "adist": round(adist, 2),
                "nearest_amenities": nearest_amenities,
            }
        )

    results.sort(key=lambda x: x["adist"])
    return results[:top_k]
