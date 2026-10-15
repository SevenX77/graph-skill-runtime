import { graphPayload } from './payload.js';

/** The canvas page as the Claude Mod presents it. */
export const canvasPage = {
  tool: 'mcp__graph-skill-canvas__show_graph',
  label: 'Graph Skill canvas',
  command: { name: 'graph-skill-canvas', description: 'Get the latest Graph Skill HTML canvas link' },
  // The labeled demonstration has no business root and no HTTP page.
  accepts: input => typeof input.skill_root === 'string' && input.skill_root.length > 0,
  readPayload: graphPayload,
};
