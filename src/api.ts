const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ─── Shared types ────────────────────────────────────────────────────────────

export interface AmenityType {
  id: number;
  type_code: string;
  display_name: string;
  default_weight: number;
}

export interface AmenityPoint {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  type_code: string;
  display_name: string;
}

export interface NearestAmenity {
  name: string;
  distance_m: number;
}

export interface ApartmentResult {
  id: number;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  price_m2: number | null;
  adist: number;
  nearest_amenities: Record<string, NearestAmenity>;
}

// ─── Trace types (for /search/visualize) ─────────────────────────────────────

export interface TreeNodeMeta {
  node_id: number;
  mbr: { min_lat: number; max_lat: number; min_lon: number; max_lon: number };
  level: number;
  is_leaf: boolean;
}

export type TraceStepType = "visit" | "prune" | "leaf" | "topk_update";

export interface TraceStep {
  type: TraceStepType;
  // visit / prune / leaf
  node_id?: number;
  amindist?: number;
  best_k_dist?: number;
  // leaf
  apartments?: { id: number; adist: number }[];
  // topk_update
  apt_id?: number;
  adist?: number;
}

export interface TraceStats {
  nodes_visited: number;
  nodes_pruned: number;
  apartments_checked: number;
  total_apartments: number;
}

export interface AlgoTrace {
  apt_tree_nodes: TreeNodeMeta[];
  steps: TraceStep[];
  stats: TraceStats;
}

export interface VisualizeResult {
  results: ApartmentResult[];
  trace: AlgoTrace;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function fetchAmenityTypes(): Promise<AmenityType[]> {
  const res = await fetch(`${API}/amenity-types`);
  if (!res.ok) throw new Error("Failed to fetch amenity types");
  return res.json();
}

export async function fetchAmenities(typeCode: string): Promise<AmenityPoint[]> {
  const res = await fetch(`${API}/amenities?type_code=${encodeURIComponent(typeCode)}`);
  if (!res.ok) throw new Error(`Failed to fetch amenities for ${typeCode}`);
  return res.json();
}

export async function fetchAllApartments(): Promise<ApartmentResult[]> {
  const res = await fetch(`${API}/apartments`);
  if (!res.ok) throw new Error("Failed to fetch apartments");
  return res.json();
}

export async function searchApartments(
  weights: Record<string, number>,
  topK: number,
): Promise<ApartmentResult[]> {
  const res = await fetch(`${API}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weights, top_k: topK }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail ?? "Search failed");
  }
  return res.json();
}

export async function searchVisualize(
  weights: Record<string, number>,
  topK: number,
): Promise<VisualizeResult> {
  const res = await fetch(`${API}/search/visualize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weights, top_k: topK }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail ?? "Visualize search failed");
  }
  return res.json();
}
