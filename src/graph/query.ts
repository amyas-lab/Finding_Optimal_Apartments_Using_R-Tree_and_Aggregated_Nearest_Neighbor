import type { GraphNode, Query } from "./types";

// Each condition checks one field on a node's data bag.
// A query is a list of conditions — all must pass (AND logic).
// OR logic, nested trees, graph-traversal conditions: future work.

export function matchNode(node: GraphNode, query: Query): boolean {
  return query.every((condition) => {
    const val = node.data[condition.field];
    switch (condition.op) {
      case "eq":
        return val === condition.value;
      case "contains":
        return Array.isArray(val) && val.includes(condition.value);
      case "gte":
        return typeof val === "number" && val >= (condition.value as number);
      case "lte":
        return typeof val === "number" && val <= (condition.value as number);
      default:
        return false;
    }
  });
}

export function queryGraph(nodes: GraphNode[], query: Query): GraphNode[] {
  return nodes.filter((n) => matchNode(n, query));
}
