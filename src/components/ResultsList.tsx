import type { ApartmentResult } from "../api";

interface Props {
  results: ApartmentResult[] | null;
  loading: boolean;
}

const MEDAL: Record<number, string> = { 0: "🥇", 1: "🥈", 2: "🥉" };

const TYPE_ICONS: Record<string, string> = {
  hospital: "🏥",
  school: "🏫",
  supermarket: "🛒",
  park: "🌳",
};

function formatPrice(p: number | null) {
  if (p == null) return "—";
  return (p / 1_000_000).toFixed(1) + " M ₫/m²";
}

function formatDist(m: number) {
  return m >= 1000 ? (m / 1000).toFixed(1) + " km" : Math.round(m) + " m";
}

export default function ResultsList({ results, loading }: Props) {
  if (loading) {
    return (
      <div style={centerStyle}>
        <span style={{ fontSize: 32 }}>⏳</span>
        <p style={{ color: "#888", marginTop: 12 }}>Searching…</p>
      </div>
    );
  }

  if (results === null) {
    return (
      <div style={centerStyle}>
        <span style={{ fontSize: 48 }}>🏙️</span>
        <p style={{ color: "#555", marginTop: 12, maxWidth: 320, textAlign: "center", lineHeight: 1.6 }}>
          Select amenity types on the left, adjust weights, then click <strong style={{ color: "#7c3aed" }}>Search</strong>.
        </p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div style={centerStyle}>
        <span style={{ fontSize: 32 }}>🔍</span>
        <p style={{ color: "#888", marginTop: 12 }}>No apartments found.</p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ margin: "0 0 4px", fontSize: 13, color: "#666" }}>
        Top {results.length} apartment{results.length !== 1 ? "s" : ""} by aggregate distance
      </p>

      {results.map((apt, i) => (
        <div
          key={apt.id}
          style={{
            background: "#1a1a2e",
            border: i === 0 ? "1px solid #7c3aed" : "1px solid #2e303a",
            borderRadius: 10,
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {/* Header row */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
            <span style={{ fontSize: 22, lineHeight: 1 }}>
              {MEDAL[i] ?? `#${i + 1}`}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: "#e2e8f0", fontSize: 15 }}>
                {apt.name}
              </div>
              <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
                {apt.address}
              </div>
            </div>
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div style={{ fontSize: 13, color: "#a78bfa", fontWeight: 600 }}>
                {formatDist(apt.adist)}
              </div>
              <div style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
                adist
              </div>
            </div>
          </div>

          {/* Stats row */}
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Chip label="Price" value={formatPrice(apt.price_m2)} />
            <Chip label="Lat" value={apt.latitude.toFixed(5)} />
            <Chip label="Lon" value={apt.longitude.toFixed(5)} />
          </div>

          {/* Nearest amenities */}
          {Object.keys(apt.nearest_amenities).length > 0 && (
            <div
              style={{
                borderTop: "1px solid #2e303a",
                paddingTop: 10,
                display: "flex",
                flexDirection: "column",
                gap: 5,
              }}
            >
              <p style={{ margin: 0, fontSize: 11, color: "#555", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Nearest amenities
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {Object.entries(apt.nearest_amenities).map(([code, info]) => (
                  <div
                    key={code}
                    style={{
                      fontSize: 12,
                      background: "#111",
                      border: "1px solid #2e303a",
                      borderRadius: 6,
                      padding: "4px 8px",
                      color: "#9ca3af",
                      display: "flex",
                      gap: 5,
                      alignItems: "center",
                    }}
                  >
                    <span>{TYPE_ICONS[code] ?? "📍"}</span>
                    <span style={{ color: "#e2e8f0" }}>{info.name}</span>
                    <span style={{ color: "#7c3aed", fontWeight: 600 }}>
                      {formatDist(info.distance_m)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ fontSize: 12, color: "#9ca3af" }}>
      <span style={{ color: "#555" }}>{label}: </span>
      <span>{value}</span>
    </div>
  );
}

const centerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  minHeight: 300,
};
