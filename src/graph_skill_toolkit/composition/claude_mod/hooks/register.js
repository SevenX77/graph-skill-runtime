import { registerPluginBase } from '../../../plugin_base/claude_mod/index.js';
import { canvasPage } from '../../../apps/graph_canvas/claude_mod/page.js';
import { labPage } from '../../../apps/interface_lab/claude_mod/page.js';

// One Mod per installed toolkit: the Plugin Base hooks run once and present
// every page this toolkit's server can return.
export function register(on) {
  registerPluginBase(on, { pages: [canvasPage, labPage] });
}
