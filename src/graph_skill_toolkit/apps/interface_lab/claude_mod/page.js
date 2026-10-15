/** Read the lab payload from an open_interface_lab tool result as the Mod sees it. */
function labPayload(result) {
  const value = result.result;
  if (value?.structuredContent) return value.structuredContent;
  if (value?.lab) return value;
  const blocks = Array.isArray(value) ? value : value?.content;
  if (Array.isArray(blocks)) for (const block of blocks) {
    if (block.type !== 'text') continue;
    try { const data = JSON.parse(block.text); if (data?.lab) return data; } catch {}
  }
  throw new Error('The tool returned no Interface Lab data.');
}

/** The Interface Lab page as the Claude Mod presents it. */
export const labPage = {
  tool: 'mcp__graph-skill-canvas__open_interface_lab',
  label: 'Plugin Interface Lab',
  command: { name: 'plugin-interface-lab', description: 'Get the latest Plugin Interface Lab HTML link' },
  readPayload: labPayload,
};
