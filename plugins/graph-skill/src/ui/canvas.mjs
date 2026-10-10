import { z } from "zod";

const viewSchema = z.object({
  id: z.string(), width: z.number().positive().finite(), height: z.number().positive().finite(),
  nodes: z.array(z.object({ id: z.string(), label: z.string(), kind: z.string(), x: z.number().nonnegative().finite(), y: z.number().nonnegative().finite() })).nonempty(),
  edges: z.array(z.object({ from: z.string(), to: z.string() })),
});

export function validateCanvas(payload) {
  const value = viewSchema.parse(payload?.graph);
  const root = payload?.skillRoot;
  if (root !== null && (typeof root !== "string" || !root)) throw new Error("Missing Skill path.");
  const ids = new Set(value.nodes.map(node => node.id));
  if (ids.size !== value.nodes.length || value.edges.some(edge => !ids.has(edge.from) || !ids.has(edge.to))) throw new Error("Invalid canvas node references.");
  if (value.nodes.some(node => node.x + 224 > value.width || node.y + 96 > value.height)) throw new Error("Node outside canvas bounds.");
  return { graph: value, skillRoot: root };
}

// The only graph renderer. Adapters supply data and capabilities, never markup.
export function createCanvas(document) {
  const svg = document.querySelector("svg");
  const pathButton = document.querySelector("#skill-path");
  const status = document.querySelector("#status");
  const state = document.documentElement.dataset;
  let skillRoot = null, adapter = null, connected = false;
  state.connection = "standalone";
  const element = (tag, attrs, text) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function updatePath() {
    pathButton.textContent = skillRoot ?? "示例画布 · 未选择 Skill";
    pathButton.title = skillRoot ? `${adapter?.rootActionLabel ?? "Skill 文件夹"}：${skillRoot}` : "调用 show_graph 并提供 skill_root 以显示实际 Skill";
    pathButton.disabled = !skillRoot || !connected || !adapter?.openRoot;
  }
  function fail(error) {
    svg.querySelector("[data-graph]")?.remove();
    skillRoot = null;
    updatePath();
    state.toolResult = "invalid";
    status.textContent = error.message || String(error);
  }
  function receive(payload) {
    try {
      const { graph: value, skillRoot: root } = validateCanvas(payload);
      const layer = element("g", { "data-graph": value.id });
      const nodes = new Map(value.nodes.map(node => [node.id, node]));
      for (const edge of value.edges) {
        const from = nodes.get(edge.from), to = nodes.get(edge.to);
        layer.append(element("path", {
          d: `M ${from.x + 112} ${from.y + 96} C ${from.x + 112} ${(from.y + 96 + to.y) / 2}, ${to.x + 112} ${(from.y + 96 + to.y) / 2}, ${to.x + 112} ${to.y - 8}`,
          class: "edge", "marker-end": "url(#arrow)", "data-edge": `${edge.from}:${edge.to}`,
        }));
      }
      for (const node of value.nodes) {
        const group = element("g", { transform: `translate(${node.x} ${node.y})`, "data-node": node.id });
        group.append(element("rect", { width: 224, height: 96, rx: 14, class: "node" }));
        group.append(element("title", {}, `${node.kind}: ${node.label}`));
        group.append(element("circle", { cx: 24, cy: 27, r: 4, class: `dot ${node.kind.toLowerCase()}` }));
        group.append(element("text", { x: 38, y: 31, class: "kind" }, node.kind));
        group.append(element("text", { x: 22, y: 65, class: "label", ...(node.label.length > 18 ? { textLength: 180, lengthAdjust: "spacingAndGlyphs" } : {}) }, node.label));
        layer.append(group);
      }
      svg.querySelector("[data-graph]")?.remove();
      svg.append(layer);
      svg.setAttribute("viewBox", `0 0 ${value.width} ${value.height}`);
      document.querySelector("#graph-title").textContent = value.id;
      document.querySelector("#graph-description").textContent = `${value.nodes.length} nodes, ${value.edges.length} edges.`;
      skillRoot = root;
      updatePath();
      status.textContent = "";
      state.toolResult = "received";
    } catch (error) { fail(error); }
  }
  pathButton.addEventListener("click", async () => {
    const root = skillRoot;
    if (!connected || !root || !adapter?.openRoot) return;
    pathButton.disabled = true;
    try {
      const message = await adapter.openRoot(root);
      if (root === skillRoot) status.textContent = message;
    } catch (error) { if (root === skillRoot) status.textContent = error.message; }
    finally { updatePath(); }
  });
  return {
    receive, fail,
    async connect(host) {
      adapter = host;
      state.connection = "connecting";
      status.textContent = "正在连接画布…";
      try {
        await host.connect({ receive, fail });
        connected = true;
        state.connection = "connected";
        updatePath();
      } catch (error) { state.connection = "failed"; throw error; }
    },
  };
}
