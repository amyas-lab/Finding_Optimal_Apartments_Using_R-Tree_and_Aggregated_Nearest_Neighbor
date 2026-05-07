import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Rectangle,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

import AmenitySelector from "../components/AmenitySelector";
import {
  fetchAmenityTypes,
  fetchAmenities,
  fetchAllApartments,
  searchVisualize,
} from "../api";
import type {
  AmenityType,
  AmenityPoint,
  ApartmentResult,
  TreeNodeMeta,
  TraceStep,
  AlgoTrace,
} from "../api";

// ── colour helpers ─────────────────────────────────────────────────────────────

const AMENITY_COLORS: Record<string, string> = {
  hospital: "#ef4444",
  pharmacy: "#f97316",
  school: "#eab308",
  university: "#84cc16",
  supermarket: "#06b6d4",
  restaurant: "#8b5cf6",
  park: "#22c55e",
  gym: "#ec4899",
  bus_stop: "#94a3b8",
  highway: "#64748b",
};

function amenityColor(typeCode: string) {
  return AMENITY_COLORS[typeCode] ?? "#aaa";
}

// ── Map auto-fit ───────────────────────────────────────────────────────────────

function FitBounds({ apartments }: { apartments: ApartmentResult[] }) {
  const map = useMap();
  useEffect(() => {
    if (apartments.length === 0) return;
    const lats = apartments.map((a) => a.latitude);
    const lons = apartments.map((a) => a.longitude);
    map.fitBounds(
      [
        [Math.min(...lats) - 0.01, Math.min(...lons) - 0.01],
        [Math.max(...lats) + 0.01, Math.max(...lons) + 0.01],
      ],
      { animate: false },
    );
  }, [apartments, map]);
  return null;
}

// ── Derive per-node status from trace steps up to stepIdx ─────────────────────

type NodeStatus = "idle" | "visited" | "pruned" | "leaf";

function deriveNodeStatuses(
  nodes: TreeNodeMeta[],
  steps: TraceStep[],
  upTo: number,
): Record<number, NodeStatus> {
  const status: Record<number, NodeStatus> = {};
  nodes.forEach((n) => (status[n.node_id] = "idle"));
  for (let i = 0; i <= upTo && i < steps.length; i++) {
    const s = steps[i];
    if (s.type === "visit" && s.node_id != null)
      status[s.node_id] = "visited";
    else if (s.type === "prune" && s.node_id != null)
      status[s.node_id] = "pruned";
    else if (s.type === "leaf" && s.node_id != null)
      status[s.node_id] = "leaf";
  }
  return status;
}

function deriveTopKIds(steps: TraceStep[], upTo: number): Set<number> {
  const ids = new Set<number>();
  for (let i = 0; i <= upTo && i < steps.length; i++) {
    const s = steps[i];
    if (s.type === "topk_update" && s.apt_id != null) ids.add(s.apt_id);
  }
  return ids;
}

function nodeColor(status: NodeStatus): string {
  switch (status) {
    case "visited": return "#facc15";
    case "pruned":  return "#ef4444";
    case "leaf":    return "#22c55e";
    default:        return "#334155";
  }
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Visualizer() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // ── search params from URL ──
  const initWeights: Record<string, number> = (() => {
    try { return JSON.parse(searchParams.get("weights") ?? "{}"); }
    catch { return {}; }
  })();
  const initTopK = Number(searchParams.get("topK") ?? 5);

  // ── state ──
  const [amenityTypes, setAmenityTypes] = useState<AmenityType[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [weights, setWeights] = useState<Record<string, number>>(initWeights);
  const [topK, setTopK] = useState(initTopK);

  const [allApartments, setAllApartments] = useState<ApartmentResult[]>([]);
  const [amenityPoints, setAmenityPoints] = useState<AmenityPoint[]>([]);

  const [results, setResults] = useState<ApartmentResult[]>([]);
  const [trace, setTrace] = useState<AlgoTrace | null>(null);

  const [stepIdx, setStepIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const playRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── load amenity types + all apartments once ──
  useEffect(() => {
    fetchAmenityTypes().then((types) => {
      setAmenityTypes(types);
      const sel: Record<string, boolean> = {};
      const w: Record<string, number> = {};
      types.forEach((t) => {
        sel[t.type_code] = t.type_code in initWeights;
        w[t.type_code] = initWeights[t.type_code] ?? t.default_weight;
      });
      setSelected(sel);
      setWeights(w);
    });
    fetchAllApartments().then(setAllApartments);
  }, []);

  // ── load amenity points for selected types ──
  useEffect(() => {
    const active = Object.keys(selected).filter((k) => selected[k]);
    if (active.length === 0) { setAmenityPoints([]); return; }
    Promise.all(active.map((tc) => fetchAmenities(tc))).then((arrays) =>
      setAmenityPoints(arrays.flat()),
    );
  }, [selected]);

  // ── play/pause logic ──
  const stopPlay = useCallback(() => {
    if (playRef.current) clearTimeout(playRef.current);
    setPlaying(false);
  }, []);

  useEffect(() => {
    if (!playing || !trace) return;
    const maxStep = trace.steps.length - 1;
    if (stepIdx >= maxStep) { stopPlay(); return; }
    playRef.current = setTimeout(() => {
      setStepIdx((i) => Math.min(i + 1, maxStep));
    }, 600 / speed);
    return () => { if (playRef.current) clearTimeout(playRef.current); };
  }, [playing, stepIdx, trace, speed, stopPlay]);

  // ── run visualize ──
  async function handleRun() {
    const activeWeights = Object.fromEntries(
      Object.entries(weights).filter(([k]) => selected[k]),
    );
    if (Object.keys(activeWeights).length === 0) return;
    stopPlay();
    setLoading(true);
    setError(null);
    setTrace(null);
    setResults([]);
    setStepIdx(0);
    try {
      const data = await searchVisualize(activeWeights, topK);
      setResults(data.results);
      setTrace(data.trace);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const activeCount = Object.values(selected).filter(Boolean).length;
  const totalSteps = trace ? trace.steps.length : 0;
  const nodeStatuses = trace
    ? deriveNodeStatuses(trace.apt_tree_nodes, trace.steps, stepIdx)
    : {};
  const topKIds = trace
    ? deriveTopKIds(trace.steps, stepIdx)
    : new Set<number>();

  // stats up to current step
  const statsUpTo = (() => {
    if (!trace) return { visited: 0, pruned: 0, checked: 0 };
    let visited = 0, pruned = 0, checked = 0;
    for (let i = 0; i <= stepIdx && i < trace.steps.length; i++) {
      const s = trace.steps[i];
      if (s.type === "visit") visited++;
      else if (s.type === "prune") pruned++;
      else if (s.type === "leaf" && s.apartments) checked += s.apartments.length;
    }
    return { visited, pruned, checked };
  })();

  const bruteForce = trace ? trace.stats.total_apartments : 0;
  const pctFaster =
    bruteForce > 0 && statsUpTo.checked < bruteForce
      ? Math.round((1 - statsUpTo.checked / bruteForce) * 100)
      : 0;

  // apartment id → result rank
  const rankMap: Record<number, number> = {};
  results.forEach((r, i) => (rankMap[r.id] = i + 1));

  return (
    <div style={{ display: "flex", width: "100vw", height: "100vh", fontFamily: "system-ui,'Segoe UI',sans-serif", overflow: "hidden", background: "#0f0f1a" }}>

      {/* ── Map (left 70%) ── */}
      <div style={{ flex: "0 0 70%", position: "relative" }}>
        <MapContainer
          center={[10.85, 106.775]}
          zoom={13}
          style={{ width: "100%", height: "100%" }}
          zoomControl={true}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
          />

          {allApartments.length > 0 && (
            <FitBounds apartments={allApartments} />
          )}

          {/* R-tree MBR rectangles */}
          {trace &&
            trace.apt_tree_nodes.map((node) => {
              const status = nodeStatuses[node.node_id] ?? "idle";
              if (status === "idle") return null;
              const color = nodeColor(status);
              return (
                <Rectangle
                  key={node.node_id}
                  bounds={[
                    [node.mbr.min_lat, node.mbr.min_lon],
                    [node.mbr.max_lat, node.mbr.max_lon],
                  ]}
                  pathOptions={{
                    color,
                    weight: node.is_leaf ? 2 : 1,
                    fillOpacity: status === "pruned" ? 0.08 : 0.04,
                    opacity: status === "pruned" ? 0.4 : 0.8,
                    dashArray: status === "pruned" ? "4 4" : undefined,
                  }}
                >
                  <Tooltip sticky>
                    Node {node.node_id} · L{node.level} ·{" "}
                    {node.is_leaf ? "leaf" : "internal"} · {status}
                  </Tooltip>
                </Rectangle>
              );
            })}

          {/* All apartments (gray) */}
          {allApartments.map((apt) => {
            const inTopK = topKIds.has(apt.id);
            const rank = rankMap[apt.id];
            return (
              <CircleMarker
                key={apt.id}
                center={[apt.latitude, apt.longitude]}
                radius={inTopK ? 9 : 5}
                pathOptions={{
                  color: inTopK ? "#f59e0b" : "#475569",
                  fillColor: inTopK ? "#fbbf24" : "#1e293b",
                  fillOpacity: inTopK ? 0.95 : 0.6,
                  weight: inTopK ? 2 : 1,
                }}
              >
                <Tooltip>
                  {rank ? `#${rank} ` : ""}
                  {apt.name}
                  {inTopK && apt.adist != null
                    ? ` — adist: ${apt.adist}m`
                    : ""}
                </Tooltip>
              </CircleMarker>
            );
          })}

          {/* Amenity markers */}
          {amenityPoints.map((a) => (
            <CircleMarker
              key={a.id}
              center={[a.latitude, a.longitude]}
              radius={4}
              pathOptions={{
                color: amenityColor(a.type_code),
                fillColor: amenityColor(a.type_code),
                fillOpacity: 0.7,
                weight: 1,
              }}
            >
              <Tooltip>{a.display_name}: {a.name}</Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* Map legend */}
        <div style={{
          position: "absolute", bottom: 16, left: 16, zIndex: 1000,
          background: "rgba(15,15,26,0.88)", borderRadius: 8, padding: "10px 14px",
          fontSize: 11, color: "#94a3b8", display: "flex", flexDirection: "column", gap: 4,
          pointerEvents: "none",
        }}>
          {[
            { color: "#facc15", label: "Visited node" },
            { color: "#ef4444", label: "Pruned node" },
            { color: "#22c55e", label: "Leaf node" },
            { color: "#fbbf24", label: "Top-K apartment" },
            { color: "#475569", label: "Apartment" },
          ].map(({ color, label }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* ── Right panel (30%) ── */}
      <div style={{
        flex: "0 0 30%",
        display: "flex",
        flexDirection: "column",
        background: "#0f0f1a",
        borderLeft: "1px solid #2e303a",
        overflowY: "auto",
        color: "#ccc",
      }}>
        {/* Header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid #2e303a", display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => navigate("/")}
            style={{ background: "none", border: "none", color: "#60a5fa", cursor: "pointer", fontSize: 13, padding: 0 }}
          >
            ← Back
          </button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#e2e8f0" }}>
            Algorithm Visualizer
          </h2>
        </div>

        <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Amenity selector */}
          <AmenitySelector
            types={amenityTypes}
            selected={selected}
            weights={weights}
            onToggle={(code) => setSelected((s) => ({ ...s, [code]: !s[code] }))}
            onWeight={(code, val) => setWeights((w) => ({ ...w, [code]: val }))}
          />

          <hr style={{ border: "none", borderTop: "1px solid #2e303a", margin: 0 }} />

          {/* Top-K */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <label style={{ fontSize: 13, color: "#888" }}>Top-K</label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              style={{ marginLeft: "auto", background: "#1a1a2e", color: "#e2e8f0", border: "1px solid #3e404a", borderRadius: 5, padding: "4px 8px", fontSize: 13 }}
            >
              {[3, 5, 8, 10].map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={activeCount === 0 || loading}
            style={{
              padding: "11px 0", borderRadius: 7, border: "none",
              fontWeight: 700, fontSize: 14,
              cursor: activeCount === 0 || loading ? "not-allowed" : "pointer",
              background: activeCount === 0 || loading ? "#1e1e2e" : "#7c3aed",
              color: activeCount === 0 || loading ? "#444" : "#fff",
            }}
          >
            {loading ? "Running…" : "Run & Visualize"}
          </button>

          {error && <p style={{ margin: 0, fontSize: 12, color: "#f87171" }}>{error}</p>}

          {/* Step controls */}
          {trace && (
            <>
              <hr style={{ border: "none", borderTop: "1px solid #2e303a", margin: 0 }} />

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#888" }}>
                  <span>Step {stepIdx + 1} / {totalSteps}</span>
                  <span style={{ color: nodeColor((() => {
                    const s = trace.steps[stepIdx];
                    if (!s) return "idle";
                    if (s.type === "visit") return "visited";
                    if (s.type === "prune") return "pruned";
                    if (s.type === "leaf") return "leaf";
                    return "idle";
                  })()) }}>
                    {trace.steps[stepIdx]?.type ?? ""}
                  </span>
                </div>

                <input
                  type="range"
                  min={0}
                  max={totalSteps - 1}
                  value={stepIdx}
                  onChange={(e) => { stopPlay(); setStepIdx(Number(e.target.value)); }}
                  style={{ width: "100%", accentColor: "#7c3aed" }}
                />

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <button
                    onClick={() => { setStepIdx(0); stopPlay(); }}
                    style={btnStyle}
                    title="Reset"
                  >⏮</button>
                  <button
                    onClick={() => { stopPlay(); setStepIdx((i) => Math.max(i - 1, 0)); }}
                    style={btnStyle}
                  >‹</button>
                  <button
                    onClick={() => setPlaying((p) => !p)}
                    style={{ ...btnStyle, flex: 1, background: playing ? "#1e293b" : "#7c3aed", color: "#fff" }}
                  >{playing ? "⏸ Pause" : "▶ Play"}</button>
                  <button
                    onClick={() => { stopPlay(); setStepIdx((i) => Math.min(i + 1, totalSteps - 1)); }}
                    style={btnStyle}
                  >›</button>
                  <button
                    onClick={() => { setStepIdx(totalSteps - 1); stopPlay(); }}
                    style={btnStyle}
                    title="End"
                  >⏭</button>
                </div>

                {/* Speed */}
                <div style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12, color: "#888" }}>
                  <span>Speed:</span>
                  {[0.5, 1, 2, 4].map((s) => (
                    <button
                      key={s}
                      onClick={() => setSpeed(s)}
                      style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 11, border: "1px solid #3e404a", cursor: "pointer",
                        background: speed === s ? "#7c3aed" : "#1a1a2e",
                        color: speed === s ? "#fff" : "#94a3b8",
                      }}
                    >{s}×</button>
                  ))}
                </div>
              </div>

              <hr style={{ border: "none", borderTop: "1px solid #2e303a", margin: 0 }} />

              {/* Stats */}
              <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
                <p style={{ margin: 0, fontWeight: 600, color: "#e2e8f0", fontSize: 13 }}>Stats</p>
                {[
                  { label: "Nodes visited", val: statsUpTo.visited },
                  { label: "Nodes pruned", val: statsUpTo.pruned },
                  { label: "Apts checked", val: `${statsUpTo.checked} / ${bruteForce}` },
                  { label: "Faster than brute", val: `${pctFaster}%`, color: "#22c55e" },
                ].map(({ label, val, color }) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#888" }}>{label}</span>
                    <span style={{ color: color ?? "#e2e8f0", fontWeight: 600 }}>{val}</span>
                  </div>
                ))}
              </div>

              <hr style={{ border: "none", borderTop: "1px solid #2e303a", margin: 0 }} />

              {/* Top-K results */}
              {results.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <p style={{ margin: 0, fontWeight: 600, color: "#e2e8f0", fontSize: 13 }}>
                    Top-{results.length} Results
                  </p>
                  {results.map((r, i) => (
                    <div
                      key={r.id}
                      style={{
                        background: "#1a1a2e", borderRadius: 7, padding: "8px 12px",
                        border: topKIds.has(r.id) ? "1px solid #f59e0b" : "1px solid #2e303a",
                        fontSize: 12,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                        <span style={{ fontWeight: 700, color: "#e2e8f0" }}>
                          {["🥇","🥈","🥉"][i] ?? `#${i+1}`} {r.name}
                        </span>
                        <span style={{ color: "#f59e0b", fontWeight: 600 }}>{r.adist}m</span>
                      </div>
                      <div style={{ color: "#555", fontSize: 11 }}>{r.address}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: "#1a1a2e",
  border: "1px solid #3e404a",
  color: "#94a3b8",
  borderRadius: 5,
  padding: "4px 10px",
  cursor: "pointer",
  fontSize: 14,
};
