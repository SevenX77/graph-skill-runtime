/** Read the Graph Skill payload from a show_graph tool result as the Mod sees it. */
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
