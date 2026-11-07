import { registerPluginBase } from 'hostpane/claude-mod';
import { canvasPage } from '../../../apps/graph_canvas/claude_mod/page.js';
import { labPage } from '../../../apps/interface_lab/claude_mod/page.js';

// One Mod per installed toolkit: the Plugin Base hooks run once and present
// every page this toolkit's server can return.
export function register(on) {
  registerPluginBase(on, { pluginName: 'graph-skill-canvas-mod', pages: [canvasPage, labPage] });
}
