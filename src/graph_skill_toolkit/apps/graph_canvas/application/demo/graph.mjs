// A protocol probe fixture, not a user skill or a runtime graph contract.
export const graph = Object.freeze({
  id: "graph-skill-canvas-probe",
  nodes: Object.freeze([
    Object.freeze({ id: "input", label: "Input", kind: "INPUT", x: 64, y: 56 }),
    Object.freeze({ id: "process", label: "Process", kind: "LOGIC", x: 64, y: 226 }),
    Object.freeze({ id: "output", label: "Output", kind: "OUTPUT", x: 64, y: 396 }),
  ]),
  edges: Object.freeze([
    Object.freeze({ from: "input", to: "process" }),
    Object.freeze({ from: "process", to: "output" }),
  ]),
});

// JSON object key ordering can change while a result passes through a host.
export function matchesProbeGraph(value) {
  const matchesItems = (actual, expected) => Array.isArray(actual)
    && actual.length === expected.length
    && expected.every((item, index) => Object.entries(item).every(([key, field]) => actual[index]?.[key] === field));
  return value?.id === graph.id
    && matchesItems(value.nodes, graph.nodes)
    && matchesItems(value.edges, graph.edges);
}
