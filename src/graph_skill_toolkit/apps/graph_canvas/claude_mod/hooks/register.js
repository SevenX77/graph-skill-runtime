import { registerPluginBase } from '../../../../plugin_base/claude_mod/index.js';
import { graphPayload } from '../payload.js';

export function register(on) {
  registerPluginBase(on, { pages: [{
    tool: 'mcp__graph-skill-canvas__show_graph',
    label: 'Graph Skill canvas',
    command: { name: 'graph-skill-canvas', description: 'Get the latest Graph Skill HTML canvas link' },
    // The labeled demonstration has no business root and no HTTP page.
    accepts: input => typeof input.skill_root === 'string' && input.skill_root.length > 0,
    readPayload: graphPayload,
  }] });
}
