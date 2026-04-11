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
from typing import Dict, List, Optional, Tuple

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


# ─────────────────────────────────────────────────────────────────────────────
#  MBR-to-amenity-tree lower bound  (used by ann_search_mbm)
# ─────────────────────────────────────────────────────────────────────────────

def _mbr_to_mbr_mindist(apt_mbr, node_mbr) -> float:
    """
    Minimum possible distance between any point in apt_mbr and any point in node_mbr.

    Finds the nearest point in node_mbr to apt_mbr, then uses apt_mbr.mindist
    on that point.  Returns 0 when the two MBRs overlap.
    """
    # Nearest lat in node_mbr to apt_mbr
    if node_mbr.max_lat < apt_mbr.min_lat:
        p_lat = node_mbr.max_lat
    elif node_mbr.min_lat > apt_mbr.max_lat:
        p_lat = node_mbr.min_lat
    else:
        p_lat = (max(apt_mbr.min_lat, node_mbr.min_lat) +
                 min(apt_mbr.max_lat, node_mbr.max_lat)) / 2.0

    # Nearest lon in node_mbr to apt_mbr
    if node_mbr.max_lon < apt_mbr.min_lon:
        p_lon = node_mbr.max_lon
    elif node_mbr.min_lon > apt_mbr.max_lon:
        p_lon = node_mbr.min_lon
    else:
        p_lon = (max(apt_mbr.min_lon, node_mbr.min_lon) +
                 min(apt_mbr.max_lon, node_mbr.max_lon)) / 2.0

    return apt_mbr.mindist(p_lat, p_lon)


def _min_dist_mbr_to_tree(apt_mbr, amenity_tree: RTreeNode) -> float:
    """
    Exact lower bound: min over all amenities a in amenity_tree of mindist(apt_mbr, a).

    Traverses the amenity R-tree with branch-and-bound, pruning subtrees whose
    MBR-to-MBR mindist already exceeds the current best.

    This guarantees:
        _min_dist_mbr_to_tree(apt_mbr, T) ≤ dist(p, nearest amenity)
    for every apartment p inside apt_mbr.
    """
    best = float("inf")
    tc = 0
    heap: list = [(_mbr_to_mbr_mindist(apt_mbr, amenity_tree.mbr), tc, amenity_tree)]

    while heap:
        lb, _, node = heapq.heappop(heap)
        if lb >= best:
            break  # min-heap: nothing in queue can improve on best
        if node.is_leaf:
            for entry in node.entries:
                d = apt_mbr.mindist(entry["latitude"], entry["longitude"])
                if d < best:
                    best = d
        else:
            for child in node.children:
                child_lb = _mbr_to_mbr_mindist(apt_mbr, child.mbr)
                if child_lb < best:
                    tc += 1
                    heapq.heappush(heap, (child_lb, tc, child))

    return best


# ─────────────────────────────────────────────────────────────────────────────
#  True MBM (Minimum Bounding Method) ANN search
# ─────────────────────────────────────────────────────────────────────────────

def ann_search_mbm(
    apt_tree: Optional[RTreeNode],
    type_trees: Dict[str, Optional[RTreeNode]],
    weights: Dict[str, float],
    top_k: int = 10,
) -> List[dict]:
    """
    True MBM (Minimum Bounding Method) ANN search.

    Instead of iterating over all apartments (brute force), we traverse
    the apartment R-tree and prune entire branches using amindist lower bound.

    amindist(apt_node, Q) = Σ w_i × mindist(apt_node.mbr, nearest amenity of type i)

    If amindist(apt_node) >= current k-th best adist → prune entire branch.

    Parameters
    ----------
    apt_tree   : R-tree built on apartments (str_build(apartments))
    type_trees : {type_code: RTreeNode} — one R-tree per amenity type
    weights    : {type_code: weight}
    top_k      : number of results to return

    Returns
    -------
    List of apartment dicts enriched with 'adist' and 'nearest_amenities',
    sorted by adist ascending.
    """
    if apt_tree is None:
        return []

    active_types = {
        tc: w for tc, w in weights.items()
        if w > 0 and type_trees.get(tc) is not None
    }

    if not active_types:
        return []

    # Max-heap of size k: (-adist, tie_counter, apt_dict)
    # Negating adist turns Python's min-heap into a max-heap on adist.
    # tie_counter prevents dict comparison when two adists are equal.
    top_k_heap: list = []
    heap_counter = 0

    def best_k_dist() -> float:
        """Worst adist in the current top-k. Returns inf while heap has < k items."""
        if len(top_k_heap) < top_k:
            return float("inf")
        return -top_k_heap[0][0]

    def compute_amindist(node: RTreeNode) -> float:
        """
        amindist(node, Q) = Σ w_i × min_{a in type_i} mindist(node.mbr, a)

        For each amenity type, traverses the amenity R-tree to find the amenity
        whose point is closest to node.mbr (using mindist as the distance measure).
        This is a valid lower bound:
            amindist(node) ≤ adist(p, Q)  for every apartment p inside node.mbr
        """
        total = 0.0
        for type_code, weight in active_types.items():
            tree = type_trees[type_code]
            d = _min_dist_mbr_to_tree(node.mbr, tree)
            total += weight * d
        return total

    def compute_adist(apt: dict) -> Tuple[float, dict]:
        """Exact adist and nearest-amenity breakdown for one specific apartment."""
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
        return round(adist, 2), nearest_amenities

    # Min-heap for MBM traversal: (amindist_lower_bound, tie_counter, node)
    counter = 0
    traversal_heap: list = [(0.0, counter, apt_tree)]

    while traversal_heap:
        lb, _, node = heapq.heappop(traversal_heap)

        # Prune: lower bound already ≥ k-th best → whole subtree cannot improve results
        if lb >= best_k_dist():
            continue

        if node.is_leaf:
            for apt in node.entries:
                adist, nearest_amenities = compute_adist(apt)
                if adist < best_k_dist():
                    enriched = {**apt, "adist": adist, "nearest_amenities": nearest_amenities}
                    heap_counter += 1
                    heapq.heappush(top_k_heap, (-adist, heap_counter, enriched))
                    if len(top_k_heap) > top_k:
                        heapq.heappop(top_k_heap)
        else:
            for child in node.children:
                child_lb = compute_amindist(child)
                if child_lb < best_k_dist():
                    counter += 1
                    heapq.heappush(traversal_heap, (child_lb, counter, child))

    results = [apt for (_, _, apt) in top_k_heap]
    results.sort(key=lambda x: x["adist"])
    return results
