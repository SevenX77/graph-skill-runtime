// Presentation-only validation. Runtime compilation owns full skill validity.
// Kept independent of React so server and adapter contracts can be checked offline.
export function validateCanvas(payload) {
  const source = payload?.graph;
  const finite = value => typeof value === "number" && Number.isFinite(value);
  if (!source || typeof source.id !== "string" || !finite(source.width) || source.width <= 0 || !finite(source.height) || source.height <= 0 || !Array.isArray(source.nodes) || !source.nodes.length || !Array.isArray(source.edges)) throw new Error("Invalid canvas graph.");
  const nodes = source.nodes.map(node => {
    if (!node || typeof node.id !== "string" || typeof node.label !== "string" || typeof node.kind !== "string" || !finite(node.x) || node.x < 0 || !finite(node.y) || node.y < 0) throw new Error("Invalid canvas node.");
    return { id: node.id, label: node.label, kind: node.kind, x: node.x, y: node.y };
  });
  const edges = source.edges.map(edge => {
    if (!edge || typeof edge.from !== "string" || typeof edge.to !== "string") throw new Error("Invalid canvas edge.");
    return { from: edge.from, to: edge.to };
  });
  const root = payload?.skillRoot;
  if (root !== null && (typeof root !== "string" || !root)) throw new Error("Missing Skill path.");
  const ids = new Set(nodes.map(node => node.id));
  if (ids.size !== nodes.length || edges.some(edge => !ids.has(edge.from) || !ids.has(edge.to))) throw new Error("Invalid canvas node references.");
  if (nodes.some(node => node.x + 224 > source.width || node.y + 96 > source.height)) throw new Error("Node outside canvas bounds.");
  return { graph: { id: source.id, width: source.width, height: source.height, nodes, edges }, skillRoot: root };
}
