"""
FastAPI entry point — ApartmentGPS backend.

Endpoints
---------
GET  /amenity-types          → list of all amenity types with default weights
GET  /apartments             → list of all apartments (unranked)
POST /search                 → ANN-ranked apartment search
POST /reload                 → force-reload DB data and rebuild R-trees

Start with:
    uvicorn main:app --reload --port 8000
"""

import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from db import load_amenities_by_type, load_amenity_types, load_apartments
from rtree.build import str_build
from rtree.node import RTreeNode
from rtree.search import ann_search, ann_search_mbm

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("apartmentgps")

app = FastAPI(title="ApartmentGPS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ─────────────────────────────────────────────────────────────────────────────
#  In-memory cache — populated lazily on first request
# ─────────────────────────────────────────────────────────────────────────────

_apartments: Optional[List[dict]] = None
_apt_tree: Optional[RTreeNode] = None
_type_trees: Optional[Dict[str, Optional[RTreeNode]]] = None
_amenities_by_type: Optional[Dict[str, List[dict]]] = None
_amenity_types: Optional[List[dict]] = None


def _ensure_loaded() -> None:
    global _apartments, _apt_tree, _type_trees, _amenities_by_type, _amenity_types

    if _apartments is None:
        logger.info("Loading apartments…")
        _apartments = load_apartments()
        logger.info("  → %d apartments", len(_apartments))

    if _apt_tree is None:
        logger.info("Building apartment R-tree…")
        _apt_tree = str_build(_apartments)
        logger.info("  → apartment R-tree ready")

    if _type_trees is None:
        logger.info("Building amenity R-trees…")
        _amenities_by_type = load_amenities_by_type()
        _type_trees = {code: str_build(entries) for code, entries in _amenities_by_type.items()}
        counts = {code: len(entries) for code, entries in _amenities_by_type.items()}
        logger.info("  → trees built: %s", counts)

    if _amenity_types is None:
        _amenity_types = load_amenity_types()


# ─────────────────────────────────────────────────────────────────────────────
#  Request / response models
# ─────────────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    weights: Dict[str, float]  # {type_code: weight}  e.g. {"hospital": 0.5, "school": 0.5}
    top_k: int = 10

    @field_validator("weights")
    @classmethod
    def weights_must_be_positive(cls, v: dict) -> dict:
        if not v:
            raise ValueError("weights must not be empty")
        if any(w < 0 for w in v.values()):
            raise ValueError("all weights must be ≥ 0")
        if sum(v.values()) <= 0:
            raise ValueError("at least one weight must be > 0")
        return v

    @field_validator("top_k")
    @classmethod
    def top_k_range(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("top_k must be between 1 and 100")
        return v


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/amenity-types")
def get_amenity_types():
    """Return all amenity types with default weights for the UI weight sliders."""
    _ensure_loaded()
    return _amenity_types


@app.get("/apartments")
def get_apartments():
    """Return all apartments without ranking (useful for map initialisation)."""
    _ensure_loaded()
    return _apartments


@app.post("/search")
def search(req: SearchRequest):
    """
    Rank apartments by aggregate weighted distance to nearest amenities.

    Request body
    ────────────
    {
      "weights": {"hospital": 0.5, "school": 0.3, "supermarket": 0.2},
      "top_k": 10
    }

    Response
    ────────
    List of apartment objects (best first), each enriched with:
      "adist"             — aggregate distance in metres
      "nearest_amenities" — {type_code: {name, distance_m}}
    """
    _ensure_loaded()

    # Normalise weights so they sum to exactly 1
    total = sum(req.weights.values())
    normalised = {k: v / total for k, v in req.weights.items()}

    results = ann_search_mbm(
        apt_tree=_apt_tree,
        type_trees=_type_trees,
        weights=normalised,
        top_k=req.top_k,
    )
    return results


@app.get("/amenities")
def get_amenities(type_code: Optional[str] = None):
    """Return amenities, optionally filtered by type_code."""
    _ensure_loaded()
    if type_code:
        return _amenities_by_type.get(type_code, [])
    return [e for entries in _amenities_by_type.values() for e in entries]


@app.post("/search/visualize")
def search_visualize(req: SearchRequest):
    """
    Same as /search but also returns the full MBM algorithm trace for visualization.

    Response: { "results": [...], "trace": { "apt_tree_nodes", "steps", "stats" } }
    """
    _ensure_loaded()
    total = sum(req.weights.values())
    normalised = {k: v / total for k, v in req.weights.items()}
    return ann_search_mbm(
        apt_tree=_apt_tree,
        type_trees=_type_trees,
        weights=normalised,
        top_k=req.top_k,
        debug=True,
    )


@app.post("/reload")
def reload_data():
    """Force-reload all data from the database and rebuild R-trees."""
    global _apartments, _apt_tree, _type_trees, _amenities_by_type, _amenity_types
    _apartments = None
    _apt_tree = None
    _type_trees = None
    _amenities_by_type = None
    _amenity_types = None
    _ensure_loaded()
    return {
        "status": "ok",
        "apartments": len(_apartments),
        "amenity_types": [t["type_code"] for t in _amenity_types],
    }
