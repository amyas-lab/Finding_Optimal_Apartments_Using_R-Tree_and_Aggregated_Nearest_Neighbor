import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3-force";
import { useGraphStore } from "../graph/store";

const NODE_RADIUS = 14;
const LABEL_OFFSET = 26;
const LINK_DISTANCE = 120;
const CHARGE_STRENGTH = -200;
const CENTER_X = 400;
const CENTER_Y = 300;
const SIM_TICKS = 300;
const CIRCLE_RADIUS = 150; // initial seeding radius
const BG_COLOR = "#111";
const BG_IMG = "/bg.jpg";

interface SimNode {
  id: string;
  label: string;
  color: string;
  x: number;
  y: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimLink {
  id: string;
  source: SimNode;
  target: SimNode;
}

interface Props {
  highlightNodes?: Set<string>;
  highlightEdges?: Set<string>;
}

export default function GraphCanvas({ highlightNodes, highlightEdges }: Props) {
  const { nodes, edges } = useGraphStore();
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [simLinks, setSimLinks] = useState<SimLink[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const settle = useCallback(() => {
    // seed positions in a circle — deterministic start → consistent equilibrium
    const ns: SimNode[] = nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      return {
        id: n.id,
        label: String(n.data.label),
        color: typeof n.data.color === "string" ? n.data.color : "#888",
        x: CENTER_X + Math.cos(angle) * CIRCLE_RADIUS,
        y: CENTER_Y + Math.sin(angle) * CIRCLE_RADIUS,
      };
    });

    const ls: SimLink[] = edges
      .map((e) => ({
        id: e.id,
        source: ns.find((n) => n.id === e.source)!,
        target: ns.find((n) => n.id === e.target)!,
      }))
      .filter((l) => l.source && l.target);

    d3.forceSimulation<SimNode>(ns)
      .force("link", d3.forceLink<SimNode, SimLink>(ls).distance(LINK_DISTANCE))
      .force("charge", d3.forceManyBody().strength(CHARGE_STRENGTH))
      .force("center", d3.forceCenter(CENTER_X, CENTER_Y))
      .stop()
      .tick(SIM_TICKS);

    // pin everything — drag mutates directly, sim is never restarted
    ns.forEach((n) => {
      n.fx = n.x;
      n.fy = n.y;
    });

    setSimNodes([...ns]);
    setSimLinks([...ls]);
  }, [nodes, edges]);

  useEffect(() => {
    settle();
  }, [nodes.length, edges.length]);

  function onMouseDown(e: React.MouseEvent, node: SimNode) {
    e.stopPropagation();

    const svg = svgRef.current!;
    const rect = svg.getBoundingClientRect();
    let dragged = false;

    function onMove(me: MouseEvent) {
      dragged = true;
      node.fx = me.clientX - rect.left;
      node.fy = me.clientY - rect.top;
      node.x = node.fx;
      node.y = node.fy;
      setSimNodes((prev) => [...prev]);
    }

    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      if (!dragged) {
        setSelectedId((prev) => (prev === node.id ? null : node.id));
      }
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <div style={{ position: "absolute", top: 8, right: 8, zIndex: 10 }}>
        <button onClick={settle}>Reset layout</button>
      </div>

      <svg
        ref={svgRef}
        style={{ width: "100%", height: "100%", background: BG_COLOR }}
      >
        <image
          href={BG_IMG}
          x={0}
          y={0}
          width="100%"
          height="100%"
          preserveAspectRatio="xMidYMid slice"
          opacity={0.3}
        />
        {simLinks.map((l) => (
          <line
            key={l.id}
            x1={l.source.x}
            y1={l.source.y}
            x2={l.target.x}
            y2={l.target.y}
            stroke={highlightEdges?.has(l.id) ? "orange" : "#555"}
            strokeWidth={highlightEdges?.has(l.id) ? 3 : 1.5}
            opacity={highlightEdges && !highlightEdges.has(l.id) ? 0.2 : 1}
          />
        ))}

        {simNodes.map((n) => (
          <g
            key={n.id}
            onMouseDown={(e) => onMouseDown(e, n)}
            style={{ cursor: "grab" }}
          >
            <circle
              cx={n.x}
              cy={n.y}
              r={NODE_RADIUS}
              fill={n.color}
              stroke={
                n.id === selectedId
                  ? "white"
                  : highlightNodes?.has(n.id)
                    ? "orange"
                    : "transparent"
              }
              strokeWidth={2}
              opacity={highlightNodes && !highlightNodes.has(n.id) ? 0.3 : 1}
            />
            <text
              x={n.x}
              y={n.y + LABEL_OFFSET}
              textAnchor="middle"
              fill="#ccc"
              fontSize={11}
            >
              {n.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
