import { useEffect, useLayoutEffect, useRef } from "react";
import { UX } from "../../../../../../vendor/ui-ux-template/core/behavior/ux.js";
import type { CanvasGraph } from "./types";

interface CanvasProps {
  graph: CanvasGraph;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  stale: boolean;
}

/** Node box in graph coordinates; the projection places nodes on a 280 × 160 grid. */
export const NODE = { width: 224, height: 60 } as const;
const BADGE: Record<string, string> = { INPUT: "I", LOGIC: "L", AGENT: "A", SUBGRAPH: "S", OUTPUT: "O" };
const COLOUR: Record<string, string> = { INPUT: "var(--c1)", LOGIC: "var(--c2)", AGENT: "var(--c3)", SUBGRAPH: "var(--c4)", OUTPUT: "var(--c5)" };
export const kindColour = (kind: string) => COLOUR[kind] ?? "var(--ink3)";

/** Edge from the bottom centre of one node to the top centre of the next. */
function edgePath(from: { x: number; y: number }, to: { x: number; y: number }) {
  const x1 = from.x + NODE.width / 2, y1 = from.y + NODE.height, x2 = to.x + NODE.width / 2, y2 = to.y - 6, mid = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`;
}

/** The single graph renderer used by both hosts: an infinite canvas bound through the shared UX engine. */
export function GraphCanvas({ graph, selectedId, onSelect, stale }: CanvasProps) {
  const stage = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const view = useRef<{ fit: (animate?: boolean) => void } | null>(null);
  const nodes = new Map(graph.nodes.map(node => [node.id, node]));
  const selected = selectedId ? nodes.get(selectedId) : undefined;
  const shape = graph.id + "|" + graph.nodes.map(node => `${node.id}@${node.x},${node.y}`).join(";");

  useLayoutEffect(() => {
    if (!stage.current || !world.current || !root.current) return;
    if (!view.current) view.current = UX.canvas(stage.current, { world: world.current, panel: root.current.querySelector(".cv-side")!, root: root.current }) as { fit: (animate?: boolean) => void };
    else view.current.fit(true);
  }, [shape]);
  useLayoutEffect(() => { if (root.current) UX.paint(root.current); });
  useEffect(() => {
    // The view gives way to the detail panel when it opens and returns when it closes.
    stage.current?.querySelector("[data-node]")?.dispatchEvent(new CustomEvent(selected ? "ux:focus" : "ux:blur", { bubbles: true }));
  }, [selected?.id]);

  return <div ref={root} className={"cv-board" + (selected ? " ux-active" : "")} data-scope="graph" data-dim="none">
    <div ref={stage} className="cv-stage" data-canvas onClick={event => { if (event.target === event.currentTarget && !stage.current?.dataset.dragged) onSelect(null); }}>
      <div ref={world} className={"cv-world" + (stale ? " stale" : "")} data-graph={graph.id} style={{ width: graph.width, height: graph.height }}
        role="group" aria-label={`${graph.id}：${graph.nodes.length} 个节点，${graph.edges.length} 条连线。用 Tab 选择节点，按 Enter 查看详情。`}>
        <svg className="cv-edges" width={graph.width} height={graph.height} aria-hidden="true">
          <defs>
            <marker id="cv-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 8 4 L 0 8 Z" /></marker>
            <marker id="cv-arrow-on" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 8 4 L 0 8 Z" style={{ fill: selected ? kindColour(selected.kind) : undefined }} /></marker>
          </defs>
          {graph.edges.map((edge, index) => {
            const from = nodes.get(edge.from)!, to = nodes.get(edge.to)!;
            const on = !!selectedId && (edge.from === selectedId || edge.to === selectedId);
            return <path key={`${edge.from}:${edge.to}:${index}`} d={edgePath(from, to)} className={on ? "e on" : "e"} style={on && selected ? { stroke: kindColour(selected.kind) } : undefined} markerEnd={on ? "url(#cv-arrow-on)" : "url(#cv-arrow)"} data-edge={`${edge.from}:${edge.to}`} />;
          })}
        </svg>
        {graph.nodes.map(node => {
          const related = !selectedId || node.id === selectedId || graph.edges.some(edge => (edge.from === selectedId && edge.to === node.id) || (edge.to === selectedId && edge.from === node.id));
          return <div key={node.id} className={"cv-node" + (node.id === selectedId ? " on" : "") + (related ? "" : " off")} data-cmp data-live data-node={node.id}
            style={{ left: node.x, top: node.y, width: NODE.width, height: NODE.height, ["--col" as string]: kindColour(node.kind) }}
            role="button" tabIndex={0} aria-pressed={selectedId === node.id} aria-label={`${node.kind} 节点 ${node.label}`} title={`${node.kind}: ${node.label}`}
            onClick={() => onSelect(node.id === selectedId ? null : node.id)}
            onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(node.id); } if (event.key === "Escape") onSelect(null); }}>
            <em>{BADGE[node.kind] ?? node.kind.slice(0, 1)}</em>
            <span><b>{node.label}</b>{node.kind === "INPUT" || node.kind === "OUTPUT" ? null : <small>{node.kind}</small>}</span>
          </div>;
        })}
      </div>
    </div>
    <div className="cvz" data-keep role="group" aria-label="视图">
      <button type="button" data-cv="out" aria-label="缩小">−</button>
      <output data-cv="z">100%</output>
      <button type="button" data-cv="in" aria-label="放大">+</button>
      <button type="button" data-cv="fit">适合</button>
    </div>
    <aside className="cv-side" data-keep aria-label="所选节点">
      {selected ? <div className="cv-side-in">
        <div className="between"><span className="label">所选节点</span><button type="button" className="btn ghost sm" onClick={() => onSelect(null)} aria-label="关闭">✕</button></div>
        <h2 data-selected-node>{selected.id}</h2>
        <span className="tag" style={{ ["--col" as string]: kindColour(selected.kind) }}><i className="cv-kind-dot" />{selected.kind}</span>
        <dl className="cv-facts">
          <div><dt>上游</dt><dd>{graph.edges.filter(edge => edge.to === selected.id).map(edge => nodes.get(edge.from)?.label).join("、") || "无"}</dd></div>
          <div><dt>下游</dt><dd>{graph.edges.filter(edge => edge.from === selected.id).map(edge => nodes.get(edge.to)?.label).join("、") || "无"}</dd></div>
        </dl>
      </div> : null}
    </aside>
  </div>;
}
