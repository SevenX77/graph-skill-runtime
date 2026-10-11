export interface CanvasNode {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
}

export interface CanvasGraph {
  id: string;
  width: number;
  height: number;
  nodes: CanvasNode[];
  edges: { from: string; to: string }[];
}

export interface CanvasSnapshot {
  graph: CanvasGraph;
  skillRoot: string | null;
}
