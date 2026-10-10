const PANE = 'graph-skill-canvas';
let canvas = null;
let problem = '';

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
}

export function makeCanvas(payload) {
  const graph = payload?.graph;
  if (!graph || typeof payload.skillRoot !== 'string' || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) throw new Error('Missing real graph payload');
  if (!graph.nodes.length || typeof graph.id !== 'string' || !(graph.width > 0 && graph.height > 0) || !Number.isFinite(graph.width) || !Number.isFinite(graph.height)) throw new Error('Invalid graph bounds');
  const nodes = new Map();
  for (const node of graph.nodes) {
    if (typeof node.id !== 'string' || typeof node.label !== 'string' || typeof node.kind !== 'string' || !Number.isFinite(node.x) || !Number.isFinite(node.y) || node.x < 0 || node.y < 0 || node.x + 220 > graph.width || node.y + 72 > graph.height || nodes.has(node.id)) throw new Error('Invalid graph node');
    nodes.set(node.id, node);
  }
  const edges = graph.edges.map(edge => {
    const a = nodes.get(edge.from), b = nodes.get(edge.to);
    if (!a || !b) throw new Error('Unknown graph edge');
    return `<path d="M ${a.x+110} ${a.y+72} C ${a.x+110} ${a.y+112}, ${b.x+110} ${b.y-40}, ${b.x+110} ${b.y}" fill="none" stroke="#8598b1" stroke-width="2" marker-end="url(#arrow)"/>`;
  }).join('');
  const shapes = graph.nodes.map(node => `<g><rect x="${node.x}" y="${node.y}" width="220" height="72" rx="12" fill="${node.kind === 'LOGIC' ? '#173e36' : '#23334d'}" stroke="#7ba8c9"/><text x="${node.x+14}" y="${node.y+27}" fill="#f4f7fc" font-size="16">${escapeXml(node.label)}</text><text x="${node.x+14}" y="${node.y+52}" fill="#b9ccdf" font-size="12">${escapeXml(node.kind)} · ${escapeXml(node.id)}</text></g>`).join('');
  const source = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${graph.width} ${graph.height}"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8598b1"/></marker></defs><rect width="100%" height="100%" fill="#111923"/><g font-family="sans-serif">${edges}${shapes}</g></svg>`;
  // Conservative UTF-8 upper bound stays within the documented 128 KiB host limit.
  if (source.length * 3 > 131072) throw new Error('Graph exceeds pane SVG size limit');
  const scale = Math.min(1, 560/graph.width, 900/graph.height);
  return {root:payload.skillRoot,graph,source,width:Math.ceil(graph.width*scale),height:Math.ceil(graph.height*scale)};
}

export function graphPayload(result) {
  const value = result.result;
  if (value?.structuredContent) return value.structuredContent;
  if (value?.graph) return value;
  const blocks = Array.isArray(value) ? value : value?.content;
  if (Array.isArray(blocks)) for (const block of blocks) {
    if (block.type !== 'text') continue;
    try { const data = JSON.parse(block.text); if (data?.graph) return data; } catch {}
  }
  if (typeof value === 'string') { const data = JSON.parse(value); if (data?.graph) return data; }
  throw new Error('The tool returned no graph data.');
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await $.command.register({name:'graph-skill-canvas',description:'Open the latest Graph Skill canvas'});
    return next(e);
  });
  on('command.run', {command:'graph-skill-canvas'}, async ($) => {
    if (!canvas) return {text:problem || 'No graph has been shown in this session. Ask Claude to show your Graph Skill.'};
    await $.ui.open({id:PANE,title:'Graph Skill',focus:true,closeOnEscape:true});
    return {};
  });
  on('tool.call', {tool:'mcp__graph-skill-canvas__show_graph'}, async ($, e, next) => {
    const result = await next(e);
    if (result.deny || result.isError || result.result?.isError) return result;
    try {
      // An explicit root requests real source data; omitted roots are server demos.
      // The server resolves symlinks, so its canonical root may differ from the input.
      if (typeof e.skill_root !== 'string' || !e.skill_root) return result;
      const candidate = makeCanvas(graphPayload(result));
      canvas = candidate;
      problem = '';
      const placement = await $.ui.open({id:PANE,title:'Graph Skill',focus:true,closeOnEscape:true});
      $.ui.invalidate('ui.render');
      if (!placement.isPlaced) $.ui.log('Graph canvas is ready; open /graph-skill-canvas when a pane is available.');
    } catch (error) {
      canvas = null;
      problem = 'Unable to show the graph: ' + String(error.message || error);
      $.ui.invalidate('ui.render');
      $.ui.log(problem);
    }
    return result;
  });
  on('ui.render', {component:'Pane'}, async ($, e, next) => {
    if (e.requestId !== PANE) return next(e);
    const {Box,Text,Svg} = $.ui.resolve(e);
    if (!canvas) return Text({children:[problem || 'Waiting for a Graph Skill.']});
    return Box({flexDirection:'column',gap:1,children:[
      Text({children:[canvas.graph.id],bold:true}),
      Text({children:[canvas.root]}),
      Text({children:[`${canvas.graph.nodes.length} nodes · ${canvas.graph.edges.length} edges`]}),
      e.surface === 'desktop' ? Svg({source:canvas.source,alt:canvas.graph.nodes.map(n=>n.label).join(' → '),width:canvas.width,height:canvas.height}) : Text({children:[canvas.graph.nodes.map(n=>n.label).join(' → ')]})
    ]});
  });
}
