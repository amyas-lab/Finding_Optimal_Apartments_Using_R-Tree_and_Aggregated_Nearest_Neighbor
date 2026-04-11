# ApartmentGPS — Backend

FastAPI backend for ranking apartments in District 9, Ho Chi Minh City by proximity to amenities using the **Aggregate Nearest Neighbour (ANN)** algorithm with an **R-tree** spatial index.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| MySQL | running on `localhost:3307` |
| Database | `ApartmentGPS` (tables already created) |

---

## Setup

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure the database

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

`.env` fields:

```
DB_HOST=localhost
DB_PORT=3307
DB_NAME=ApartmentGPS
DB_USER=root
DB_PASSWORD=your_password
```

### 3. Start the server

```bash
uvicorn main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`.

Interactive docs (Swagger UI): `http://localhost:8000/docs`

---

## API Reference

### `GET /amenity-types`

Returns all amenity types with their default weights. Use this to populate the weight sliders in the UI.

**Response example:**
```json
[
  { "id": 1, "type_code": "hospital", "display_name": "Hospital", "default_weight": 0.4 },
  { "id": 2, "type_code": "school",   "display_name": "School",   "default_weight": 0.3 }
]
```

---

### `GET /apartments`

Returns all apartments without ranking. Useful for initialising the map.

**Response example:**
```json
[
  {
    "id": 1,
    "name": "Vinhomes Grand Park",
    "address": "Q9, HCMC",
    "latitude": 10.8231,
    "longitude": 106.8023,
    "price_m2": 45000000
  }
]
```

---

### `POST /search`

Ranks apartments by aggregate weighted distance to the nearest amenity of each selected type.

**Request body:**
```json
{
  "weights": {
    "hospital":    0.5,
    "school":      0.3,
    "supermarket": 0.2
  },
  "top_k": 10
}
```

- `weights` — map of `type_code → weight`. Weights are automatically normalised to sum to 1.
- `top_k` — number of results to return (1–100, default 10).

**Response example:**
```json
[
  {
    "id": 3,
    "name": "The Sun Avenue",
    "address": "...",
    "latitude": 10.7769,
    "longitude": 106.7511,
    "price_m2": 52000000,
    "adist": 412.5,
    "nearest_amenities": {
      "hospital":    { "name": "Quận 9 General Hospital", "distance_m": 350.0 },
      "school":      { "name": "Trường THPT Long Trường",  "distance_m": 620.0 },
      "supermarket": { "name": "VinMart Q9",               "distance_m": 180.0 }
    }
  }
]
```

Results are sorted by `adist` ascending — the apartment with the smallest aggregate distance to your chosen amenities appears first.

---

### `POST /reload`

Forces a full reload of apartments and amenities from the database and rebuilds all R-trees. Call this after inserting new data.

**Response:**
```json
{
  "status": "ok",
  "apartments": 42,
  "amenity_types": ["hospital", "school", "supermarket"]
}
```

---

## Project Structure

```
backend/
├── main.py          # FastAPI app, endpoints, in-memory cache
├── db.py            # MySQL queries (apartments, amenities, types)
├── requirements.txt
├── .env.example
└── rtree/
    ├── node.py      # MBR and RTreeNode dataclasses, Haversine distance
    ├── build.py     # STR (Sort-Tile-Recursive) bulk-loading algorithm
    └── search.py    # NN branch-and-bound search, ANN aggregation
```

---

## Algorithm Notes

### R-tree (STR bulk-loading)

Amenities are loaded once at startup and organised into one R-tree per amenity type using the **Sort-Tile-Recursive** algorithm:

1. Sort all points by longitude.
2. Divide into `P = ⌈√(n/M)⌉` vertical slices (M = node capacity, default 9).
3. Sort each slice by latitude, then pack consecutive groups of M points into leaf nodes.
4. Recursively tile leaf nodes into internal nodes until a single root remains.

### Nearest-neighbour search

Uses a **min-heap branch-and-bound** traversal. Each R-tree node is keyed by `mindist(MBR, query_point)` — the minimum possible distance from the query to any point inside that node. Any node whose `mindist` is already worse than the current best actual distance is pruned without visiting its children.

### Aggregate distance

For a query with amenity types `Q = {q₁, …, qₘ}` and weights `W = {w₁, …, wₘ}`:

```
adist(apartment, Q) = Σ  wᵢ · dist(apartment, nearest amenity of type qᵢ)
```

All apartments are scored and the top-k are returned sorted ascending by `adist`.

---

## Connecting to the React Frontend

In your Vite app, set the API base URL (e.g. in a `.env` file):

```
VITE_API_URL=http://localhost:8000
```

Then call the search endpoint:

```ts
const res = await fetch(`${import.meta.env.VITE_API_URL}/search`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ weights: { hospital: 0.5, school: 0.5 }, top_k: 10 }),
});
const ranked = await res.json();
```
