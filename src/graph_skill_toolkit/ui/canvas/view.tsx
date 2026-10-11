import type { CanvasGraph } from "./types";

interface CanvasProps {
  graph: CanvasGraph;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** The single graph renderer used by both host adapters. */
export function GraphCanvas({ graph, selectedId, onSelect }: CanvasProps) {
  const nodes = new Map(graph.nodes.map(node => [node.id, node]));
  return (
    <svg viewBox={`0 0 ${graph.width} ${graph.height}`} role="group" aria-labelledby="graph-title graph-description">
      <title id="graph-title">{graph.id}</title>
      <desc id="graph-description">{graph.nodes.length} 个节点，{graph.edges.length} 条连线。使用 Tab 选择节点，按 Enter 查看详情。</desc>
      <defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 8 4 L 0 8 Z" className="arrow" /></marker></defs>
      <g data-graph={graph.id}>
        {graph.edges.map((edge, index) => {
          const from = nodes.get(edge.from)!;
          const to = nodes.get(edge.to)!;
          return <path key={`${edge.from}:${edge.to}:${index}`} d={`M ${from.x + 112} ${from.y + 96} C ${from.x + 112} ${(from.y + 96 + to.y) / 2}, ${to.x + 112} ${(from.y + 96 + to.y) / 2}, ${to.x + 112} ${to.y - 8}`} className="edge" markerEnd="url(#arrow)" data-edge={`${edge.from}:${edge.to}`} />;
        })}
        {graph.nodes.map(node => (
          <g key={node.id} transform={`translate(${node.x} ${node.y})`} data-node={node.id} className="graph-node" role="button" tabIndex={0} aria-label={`${node.kind} 节点 ${node.label}`} aria-pressed={selectedId === node.id} onClick={() => onSelect(node.id)} onKeyDown={event => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onSelect(node.id);
            }
          }}>
            <rect width={224} height={96} rx={14} className="node" />
            <title>{node.kind}: {node.label}</title>
            <circle cx={24} cy={27} r={4} className={`dot ${node.kind.toLowerCase()}`} />
            <text x={38} y={31} className="kind">{node.kind}</text>
            <text x={22} y={65} className="label" {...(node.label.length > 18 ? { textLength: 180, lengthAdjust: "spacingAndGlyphs" as const } : {})}>{node.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
