import type { GraphNode, GraphEdge } from "./types";

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Build a graph from an adjacency matrix.
// matrix[i][j] = edge weight (0 or undefined = no edge).
// nodeLabels is optional — defaults to N0, N1, ...
export function fromAdjacencyMatrix(
  matrix: number[][],
  nodeLabels?: string[],
): GraphData {
  const nodes: GraphNode[] = matrix.map((_, i) => ({
    id: `n${i}`,
    position: { x: 0, y: 0 },
    data: {
      label: nodeLabels?.[i] ?? `N${i}`,
      color: "steelblue",
      tags: [],
    },
  }));

  const edges: GraphEdge[] = [];
  let edgeCounter = 0;

  for (let i = 0; i < matrix.length; i++) {
    for (let j = i + 1; j < matrix[i].length; j++) {
      const weight = matrix[i][j];
      if (weight) {
        edges.push({
          id: `e${edgeCounter++}`,
          source: nodes[i].id,
          target: nodes[j].id,
          weight,
        });
      }
    }
  }

  return { nodes, edges };
}

// Generate a random symmetric adjacency matrix.
// edgeProbability: 0–1 chance any two nodes are connected.
// maxWeight: edges get a random integer weight in [1, maxWeight].
export function randomAdjacencyMatrix(
  nodeCount: number,
  edgeProbability = 0.3,
  maxWeight = 10,
): number[][] {
  const matrix = Array.from({ length: nodeCount }, () =>
    new Array(nodeCount).fill(0),
  );

  for (let i = 0; i < nodeCount; i++) {
    for (let j = i + 1; j < nodeCount; j++) {
      if (Math.random() < edgeProbability) {
        const weight = Math.floor(Math.random() * maxWeight) + 1;
        matrix[i][j] = weight;
        matrix[j][i] = weight; // symmetric — undirected graph
      }
    }
  }

  return matrix;
}

// Convenience: generate a random graph in one call
export function randomGraph(
  nodeCount: number,
  edgeProbability = 0.3,
  maxWeight = 10,
): GraphData {
  const matrix = randomAdjacencyMatrix(nodeCount, edgeProbability, maxWeight);
  return fromAdjacencyMatrix(matrix);
}
