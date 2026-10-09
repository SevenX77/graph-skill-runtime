// Presentation projection only. Runtime compilation owns full gSkill validity.
export function projectGraph(data, kinds) {
  const phases = data.phases;
  const ids = new Set(phases.map(phase => phase.id.toLowerCase()));
  if (ids.size !== phases.length) throw new Error("Duplicate phase ids.");
  const depths = new Map([["input", 0]]);
  const pending = new Map(phases.map(phase => [phase.id, phase]));
  const registered = new Set(["input", ...pending.keys()]);
  for (const phase of phases) {
    if (!Array.isArray(phase.depends_on) || !phase.depends_on.length || new Set(phase.depends_on).size !== phase.depends_on.length || phase.depends_on.some(id => !registered.has(id)) || typeof phase.output !== "boolean") throw new Error(`Invalid dependencies or output flag for ${phase.id}.`);
  }
  while (pending.size) {
    const before = pending.size;
    for (const [id, phase] of pending) {
      if (phase.depends_on.every(dep => depths.has(dep))) {
        depths.set(id, 1 + Math.max(...phase.depends_on.map(dep => depths.get(dep))));
        pending.delete(id);
      }
    }
    if (pending.size === before) throw new Error("Graph contains a dependency cycle.");
  }
  const outputId = "$output"; // Distinct from every portable phase id.
  const outputs = phases.filter(phase => phase.output);
  if (!outputs.length) throw new Error("Graph has no output phase.");
  depths.set(outputId, 1 + Math.max(...depths.values()));
  const items = [{ id: "input", label: "Input", kind: "INPUT" }, ...phases.map(phase => ({ id: phase.id, label: phase.id, kind: kinds[phase.id] })), { id: outputId, label: "Output", kind: "OUTPUT" }];
  const rows = new Map();
  for (const item of items) {
    const depth = depths.get(item.id);
    if (!rows.has(depth)) rows.set(depth, []);
    rows.get(depth).push(item);
  }
  const width = Math.max(...[...rows.values()].map(row => row.length)) * 280 + 72;
  const nodes = items.map(item => {
    const row = rows.get(depths.get(item.id));
    return { ...item, x: (width - row.length * 280) / 2 + row.indexOf(item) * 280 + 28, y: 40 + depths.get(item.id) * 160 };
  });
  const edges = phases.flatMap(phase => phase.depends_on.map(from => ({ from, to: phase.id })));
  edges.push(...outputs.map(phase => ({ from: phase.id, to: outputId })));
  return { id: data.graph_id, nodes, edges, width, height: 176 + depths.get(outputId) * 160 };
}
