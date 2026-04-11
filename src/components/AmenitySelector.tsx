import type { AmenityType } from "../api";

interface Props {
  types: AmenityType[];
  selected: Record<string, boolean>;
  weights: Record<string, number>;
  onToggle: (code: string) => void;
  onWeight: (code: string, value: number) => void;
}

const ICONS: Record<string, string> = {
  hospital: "🏥",
  school: "🏫",
  supermarket: "🛒",
  park: "🌳",
};

export default function AmenitySelector({
  types,
  selected,
  weights,
  onToggle,
  onWeight,
}: Props) {
  const activeTotal = types
    .filter((t) => selected[t.type_code])
    .reduce((sum, t) => sum + (weights[t.type_code] ?? 1), 0);

  if (types.length === 0) {
    return <p style={{ fontSize: 13, color: "#666" }}>Loading amenity types…</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ margin: 0, fontSize: 12, color: "#888", textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Amenity types &amp; weights
      </p>

      {types.map((t) => {
        const isOn = selected[t.type_code] ?? false;
        const w = weights[t.type_code] ?? 1;
        const pct =
          isOn && activeTotal > 0
            ? Math.round((w / activeTotal) * 100)
            : null;

        return (
          <div key={t.type_code}>
            {/* Checkbox row */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer",
                userSelect: "none",
              }}
            >
              <input
                type="checkbox"
                checked={isOn}
                onChange={() => onToggle(t.type_code)}
                style={{ accentColor: "#7c3aed", width: 15, height: 15 }}
              />
              <span style={{ fontSize: 14, color: isOn ? "#e2e8f0" : "#666" }}>
                {ICONS[t.type_code] ?? "📍"} {t.display_name}
              </span>
              {pct !== null && (
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 11,
                    color: "#7c3aed",
                    fontWeight: 600,
                    background: "rgba(124,58,237,0.15)",
                    borderRadius: 4,
                    padding: "1px 5px",
                  }}
                >
                  {pct}%
                </span>
              )}
            </label>

            {/* Weight slider — only shown when checked */}
            {isOn && (
              <div style={{ paddingLeft: 23, marginTop: 6 }}>
                <input
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={w * 10}
                  onChange={(e) =>
                    onWeight(t.type_code, Number(e.target.value) / 10)
                  }
                  style={{ width: "100%", accentColor: "#7c3aed" }}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 10,
                    color: "#555",
                    marginTop: 1,
                  }}
                >
                  <span>low</span>
                  <span>weight {w.toFixed(1)}</span>
                  <span>high</span>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Normalisation note */}
      {Object.values(selected).some(Boolean) && (
        <p style={{ margin: 0, fontSize: 11, color: "#555" }}>
          Weights are normalised automatically before search.
        </p>
      )}
    </div>
  );
}
