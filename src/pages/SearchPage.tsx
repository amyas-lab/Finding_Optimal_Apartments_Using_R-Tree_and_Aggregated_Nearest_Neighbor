import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AmenitySelector from "../components/AmenitySelector";
import ResultsList from "../components/ResultsList";
import { fetchAmenityTypes, searchApartments } from "../api";
import type { AmenityType, ApartmentResult } from "../api";

export default function SearchPage() {
  const navigate = useNavigate();
  const [amenityTypes, setAmenityTypes] = useState<AmenityType[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<ApartmentResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAmenityTypes()
      .then((types) => {
        setAmenityTypes(types);
        const sel: Record<string, boolean> = {};
        const w: Record<string, number> = {};
        types.forEach((t) => {
          sel[t.type_code] = false;
          w[t.type_code] = t.default_weight;
        });
        setSelected(sel);
        setWeights(w);
      })
      .catch(() =>
        setError("Cannot reach API — is the backend running on :8000?"),
      );
  }, []);

  async function handleSearch() {
    const activeWeights = Object.fromEntries(
      Object.entries(weights).filter(([k]) => selected[k]),
    );
    if (Object.keys(activeWeights).length === 0) return;

    setLoading(true);
    setError(null);
    try {
      const data = await searchApartments(activeWeights, topK);
      setResults(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function handleVisualize() {
    const activeWeights = Object.fromEntries(
      Object.entries(weights).filter(([k]) => selected[k]),
    );
    if (Object.keys(activeWeights).length === 0) return;
    const params = new URLSearchParams({
      weights: JSON.stringify(activeWeights),
      topK: String(topK),
    });
    navigate(`/visualizer?${params.toString()}`);
  }

  const activeCount = Object.values(selected).filter(Boolean).length;

  return (
    <div
      style={{
        display: "flex",
        width: "100vw",
        height: "100vh",
        fontFamily: "system-ui, 'Segoe UI', sans-serif",
        overflow: "hidden",
      }}
    >
      {/* ── Left panel ── */}
      <div
        style={{
          width: 300,
          minWidth: 300,
          display: "flex",
          flexDirection: "column",
          gap: 16,
          padding: 20,
          overflowY: "auto",
          background: "#0f0f1a",
          borderRight: "1px solid #2e303a",
          color: "#ccc",
        }}
      >
        {/* Title */}
        <div>
          <h2 style={{ margin: 0, color: "#e2e8f0", fontSize: 18, fontWeight: 700 }}>
            🏢 ApartmentGPS
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#555" }}>
            District 9 · ANN R-tree ranking
          </p>
        </div>

        <hr style={{ border: "none", borderTop: "1px solid #2e303a", margin: 0 }} />

        <AmenitySelector
          types={amenityTypes}
          selected={selected}
          weights={weights}
          onToggle={(code) =>
            setSelected((s) => ({ ...s, [code]: !s[code] }))
          }
          onWeight={(code, val) =>
            setWeights((w) => ({ ...w, [code]: val }))
          }
        />

        <hr style={{ border: "none", borderTop: "1px solid #2e303a", margin: 0 }} />

        {/* Top-K */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label style={{ fontSize: 13, color: "#888" }}>Top-K results</label>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            style={{
              marginLeft: "auto",
              background: "#1a1a2e",
              color: "#e2e8f0",
              border: "1px solid #3e404a",
              borderRadius: 5,
              padding: "4px 8px",
              fontSize: 13,
            }}
          >
            {[3, 5, 8, 10].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>

        {/* Search button */}
        <button
          onClick={handleSearch}
          disabled={activeCount === 0 || loading}
          style={{
            padding: "11px 0",
            borderRadius: 7,
            border: "none",
            fontWeight: 700,
            fontSize: 14,
            cursor: activeCount === 0 || loading ? "not-allowed" : "pointer",
            background:
              activeCount === 0 || loading ? "#1e1e2e" : "#7c3aed",
            color: activeCount === 0 || loading ? "#444" : "#fff",
            transition: "background 0.2s",
          }}
        >
          {loading
            ? "Searching…"
            : activeCount === 0
              ? "Select at least one type"
              : `Search  (top ${topK})`}
        </button>

        {/* Visualize button */}
        <button
          onClick={handleVisualize}
          disabled={activeCount === 0}
          style={{
            padding: "11px 0",
            borderRadius: 7,
            border: "1px solid #2563eb",
            fontWeight: 600,
            fontSize: 13,
            cursor: activeCount === 0 ? "not-allowed" : "pointer",
            background: activeCount === 0 ? "#1e1e2e" : "transparent",
            color: activeCount === 0 ? "#444" : "#60a5fa",
            transition: "background 0.2s",
          }}
        >
          Visualize Algorithm →
        </button>

        {error && (
          <p style={{ margin: 0, fontSize: 12, color: "#f87171" }}>{error}</p>
        )}
      </div>

      {/* ── Right panel ── */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          background: "#111",
          padding: 24,
        }}
      >
        <ResultsList results={results} loading={loading} />
      </div>
    </div>
  );
}
