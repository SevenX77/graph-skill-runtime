import { registerPluginBase } from 'hostpane/claude-mod';
import { canvasPage } from '../../../apps/graph_canvas/claude_mod/page.js';

// One Mod per installed toolkit: the Hostpane hooks run once and present the canvas page.
export function register(on) {
  registerPluginBase(on, { pluginName: 'graph-skill-canvas-mod', pages: [canvasPage] });
}
