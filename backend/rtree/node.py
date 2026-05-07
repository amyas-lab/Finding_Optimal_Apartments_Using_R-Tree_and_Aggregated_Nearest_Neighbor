"""
MBR (Minimum Bounding Rectangle) and RTreeNode definitions.

Coordinates are stored as (latitude, longitude) in decimal degrees.
Distances are in meters.  
Mindist: is the smallest distance from the amenity (query point) to the MBR's border. 
    q = (qx, qy)
    dx = max(0, x_min - qx, qx - x_max)
    dy = max(0, q_y - y_max, y_min - qy)
    Math formula: mindist(N, q) = sqrt(dx^2 + dy^2)

MBR boundary and use the Haversine formula — accurate enough for the
small area of District 9, HCMC.

This file contains:
1. Functions:
- haversine
- mindist
- center
- expand
- from_nodes
- from_entries
2. Classes: 
- MBR
- RTreeNode
"""
import math
from dataclasses import dataclass, field
from typing import Any, List

EARTH_RADIUS_M = 6_371_000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    # Checked the Haversine formula
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass
class MBR:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    # ------------------------------------------------------------------ #
    #  Key spatial predicates                                              #
    # ------------------------------------------------------------------ #

    def mindist(self, lat: float, lon: float) -> float:
        """
        Minimum possible distance from (lat, lon) to any point inside this MBR.
        Used as the pruning lower-bound in NN search.
        """
        # Clamp query point to the rectangle boundary
        clat = max(self.min_lat, min(lat, self.max_lat))
        clon = max(self.min_lon, min(lon, self.max_lon))
        return haversine(lat, lon, clat, clon)

    def center(self) -> tuple[float, float]:
        return (self.min_lat + self.max_lat) / 2.0, (self.min_lon + self.max_lon) / 2.0

    def expand(self, other: "MBR") -> "MBR":
        """Return the smallest MBR that contains both self and other."""
        return MBR(
            min_lat=min(self.min_lat, other.min_lat),
            min_lon=min(self.min_lon, other.min_lon),
            max_lat=max(self.max_lat, other.max_lat),
            max_lon=max(self.max_lon, other.max_lon),
        )

    @classmethod
    def from_entries(cls, entries: list) -> "MBR":
        lats = [e["latitude"] for e in entries]
        lons = [e["longitude"] for e in entries]
        return cls(min(lats), min(lons), max(lats), max(lons))

    @classmethod
    def from_nodes(cls, nodes: list) -> "MBR":
        mbr = nodes[0].mbr
        for n in nodes[1:]:
            mbr = mbr.expand(n.mbr)
        return mbr


@dataclass
class RTreeNode:
    mbr: MBR
    is_leaf: bool
    # Internal node: list of child RTreeNodes
    children: List["RTreeNode"] = field(default_factory=list)
    # Leaf node: list of amenity dicts (id, name, latitude, longitude, type_code, …)
    entries: List[Any] = field(default_factory=list)
