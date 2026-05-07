"""
STR (Sort-Tile-Recursive) bulk-loading algorithm for R-trees.

Reference: Leutenegger, Lopez & Edgington (1997)
  "STR: A simple and efficient algorithm for R-tree packing"

The algorithm:
  1. Sort all n leaf entries by longitude (x).
  M: Max capacity of data samples in a node
  n: The total number of data samples
  L = number of leaf nodes L = ceil(n/M)
  2. Divide into  P = ceil(sqrt(L))) vertical slices, each of
     size P*M entries.Then Sort each slice by latitude (y).
  3. Pack consecutive groups of M entries into leaf nodes.
  4. Recursively apply the same tiling to internal nodes until a
     single root is produced.

M (capacity) defaults to 9, a common choice that keeps tree height low
for thousands of amenities.
"""

import math
from typing import Any, List, Optional

from .node import MBR, RTreeNode

DEFAULT_CAPACITY = 9


def str_build(entries: List[dict], capacity: int = DEFAULT_CAPACITY) -> Optional[RTreeNode]:
    """
    Build an R-tree from a flat list of amenity dicts using STR.

    Each dict must have 'latitude' and 'longitude' keys.
    Returns None if entries is empty.
    """
    if not entries:
        return None

    if len(entries) <= capacity:
        # Single leaf node — no tiling needed
        return RTreeNode(
            mbr=MBR.from_entries(entries),
            is_leaf=True,
            entries=list(entries),
        )

    leaves = _make_leaves(entries, capacity)
    return _pack_nodes(leaves, capacity)


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_leaves(entries: List[dict], capacity: int) -> List[RTreeNode]:
    """Sort entries spatially and pack them into leaf nodes of size ≤ capacity."""
    n = len(entries)
    num_leaves = math.ceil(n / capacity)
    # Number of vertical (longitude) slices
    P = math.ceil(math.sqrt(num_leaves))
    slice_size = P * capacity  # max entries per vertical slice

    sorted_by_lon = sorted(entries, key=lambda e: e["longitude"])

    leaves: List[RTreeNode] = []
    for i in range(0, n, slice_size):
        vertical_slice = sorted_by_lon[i : i + slice_size]
        # Within slice, sort by latitude to tile horizontally
        vertical_slice.sort(key=lambda e: e["latitude"])
        for j in range(0, len(vertical_slice), capacity):
            group = vertical_slice[j : j + capacity]
            leaves.append(
                RTreeNode(
                    mbr=MBR.from_entries(group),
                    is_leaf=True,
                    entries=group,
                )
            )
    return leaves


def _pack_nodes(nodes: List[RTreeNode], capacity: int) -> RTreeNode:
    """
    Recursively pack a list of nodes into an R-tree, returning the root.
    The tiling uses MBR-center coordinates (same STR logic as for leaves).
    """
    if len(nodes) <= capacity:
        return RTreeNode(
            mbr=MBR.from_nodes(nodes),
            is_leaf=False,
            children=nodes,
        )

    n = len(nodes)
    num_parents = math.ceil(n / capacity)
    P = math.ceil(math.sqrt(num_parents))
    slice_size = P * capacity

    # Sort internal nodes by MBR-center longitude
    sorted_by_lon = sorted(nodes, key=lambda nd: (nd.mbr.min_lon + nd.mbr.max_lon) / 2.0)

    parents: List[RTreeNode] = []
    for i in range(0, n, slice_size):
        vertical_slice = sorted_by_lon[i : i + slice_size]
        vertical_slice.sort(key=lambda nd: (nd.mbr.min_lat + nd.mbr.max_lat) / 2.0)
        for j in range(0, len(vertical_slice), capacity):
            group = vertical_slice[j : j + capacity]
            parents.append(
                RTreeNode(
                    mbr=MBR.from_nodes(group),
                    is_leaf=False,
                    children=group,
                )
            )

    return _pack_nodes(parents, capacity)
