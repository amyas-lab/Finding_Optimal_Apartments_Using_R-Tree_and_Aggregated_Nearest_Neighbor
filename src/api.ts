const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface AmenityType {
  id: number;
  type_code: string;
  display_name: string;
  default_weight: number;
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

export async function fetchAmenityTypes(): Promise<AmenityType[]> {
  const res = await fetch(`${API}/amenity-types`);
  if (!res.ok) throw new Error("Failed to fetch amenity types");
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
