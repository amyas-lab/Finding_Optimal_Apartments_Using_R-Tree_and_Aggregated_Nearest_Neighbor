import { create } from "zustand";
import type { GraphNode, GraphEdge, NodeData } from "./types";
import { randomGraph } from "./generate";

// Counters outside the store so they survive re-renders without polluting state
let nodeCounter = 0;
let edgeCounter = 0;

interface GraphStore {
  nodes: GraphNode[];
  edges: GraphEdge[];
  addNode: (data: NodeData) => void;
  addEdge: (source: string, target: string, weight?: number) => void;
  removeNode: (id: string) => void;
  setGraph: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  getEdgeId: (a: string, b: string) => string | undefined;
}

const { nodes, edges } = randomGraph(8, 0.4);

export const useGraphStore = create<GraphStore>((set) => ({
  nodes: nodes,
  edges: edges,

  setGraph: (nodes, edges) => set({ nodes, edges }),

  addNode: (data) =>
    set((state) => ({
      nodes: [
        ...state.nodes,
        {
          id: `n${++nodeCounter}`,
          position: { x: 0, y: 0 }, // canvas ignores this — d3 places it
          data,
        },
      ],
    })),

  addEdge: (source, target, weight) =>
    set((state) => ({
      edges: [
        ...state.edges,
        { id: `e${++edgeCounter}`, source, target, weight },
      ],
    })),

  getEdgeId: (a, b) => {
    const state = useGraphStore.getState();
    return state.edges.find(
      (e) =>
        (e.source === a && e.target === b) ||
        (e.source === b && e.target === a),
    )?.id;
  },

  // removing a node also prunes any edges that referenced it
  removeNode: (id) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
    })),
}));
