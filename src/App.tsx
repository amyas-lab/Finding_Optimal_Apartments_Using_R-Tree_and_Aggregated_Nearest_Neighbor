import { useState } from "react";
import GraphCanvas from "./components/GraphCanvas";
import { useGraphStore } from "./graph/store";
import { randomGraph } from "./graph/generate";

export default function App() {
  const { setGraph, getEdgeId } = useGraphStore();
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>();
  const [highlightEdges, setHighlightEdges] = useState<Set<string>>();

  function generateNew() {
    const { nodes, edges } = randomGraph(8, 0.4);
    setGraph(nodes, edges);
    setHighlightNodes(undefined);
    setHighlightEdges(undefined);
  }

  function highlight(nodeIds: string[], edgeIds: string[]) {
    setHighlightNodes(new Set(nodeIds));
    setHighlightEdges(new Set(edgeIds));
  }

  function clearHighlight() {
    setHighlightNodes(undefined);
    setHighlightEdges(undefined);
  }

  return (
    <div style={{ display: "flex", width: "100vw", height: "100vh" }}>
      {/* left panel — guide + controls */}
      <div
        style={{
          width: 280,
          padding: 16,
          overflowY: "auto",
          background: "#1a1a1a",
          color: "#ccc",
        }}
      >
        <h2 style={{ marginTop: 0 }}>ANN R-Tree</h2>
        <p>Explanation goes here.</p>

        <button
          onClick={generateNew}
          style={{ marginBottom: 8, display: "block" }}
        >
          New random graph
        </button>

        <button
          onClick={() => {
            const edgeId = getEdgeId("n0", "n2");
            highlight(["n0", "n2"], edgeId ? [edgeId] : []);
          }}
          style={{ marginBottom: 8, display: "block" }}
        >
          Test highlight
        </button>

        <button onClick={clearHighlight} style={{ display: "block" }}>
          Clear highlight
        </button>
      </div>

      {/* right panel — canvas */}
      <div style={{ flex: 1 }}>
        <GraphCanvas
          highlightNodes={highlightNodes}
          highlightEdges={highlightEdges}
        />
      </div>
    </div>
  );
}
