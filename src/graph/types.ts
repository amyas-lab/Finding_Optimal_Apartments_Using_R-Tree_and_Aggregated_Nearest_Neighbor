export interface NodeData extends Record<string, unknown> {
  label: string;
  color?: string;
  tags?: string[];
}

export interface GraphNode {
  id: string;
  position: { x: number; y: number };
  data: NodeData;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  weight?: number;
}

export interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Stub — query logic lives here later
export type QueryCondition = {
  field: string;
  op: "eq" | "gte" | "lte" | "contains";
  value: unknown;
};

export type Query = QueryCondition[];
