import { PREVIEW_TOOL, NAVIGATE_TOOL, CONTEXT_TOOL, SELECT_TOOL, bridgeDescriptor, bridgeKey, bridgePost, readHostIdentity, pollBridges, createModState, previewProjectRoot, previewTarget, browserReminder } from '../../../../plugin_base/claude_mod/index.js';
import { graphPayload } from '../payload.js';

const LABEL = 'Graph Skill canvas';

export function register(on) {
  let latestView = null, latestCanObserve = false, problem = '';
  const state = createModState();
  let timer;
  on('session.start', async ($, e, next) => {
    state.closed = false;
    timer = $.clock.every(1000, async () => { await pollBridges($, state); });
    await $.command.register({name:'graph-skill-canvas',description:'Get the latest Graph Skill HTML canvas link'});
    return next(e);
  });
  on('session.end', async ($, e, next) => {
    state.closed = true;
    state.generation++;
    if (timer) timer.cancel();
    for (const bridge of state.bridges.values()) {
      try { await bridgePost($, bridge, '/disconnect', {}); } catch { /* Stdio owner also closes the bridge. */ }
    }
    state.bridges.clear();state.contexts.clear();state.views.clear();state.seen.clear();state.receipts.clear();state.running.clear();
    return next(e);
  });
  on('command.run', {command:'graph-skill-canvas'}, async () => {
    if (!latestView) return {text:problem || 'No graph has been shown in this session. Ask Claude to show your Graph Skill.'};
    return {text:'[Graph Skill canvas](' + latestView.url + ')\n' + browserReminder(latestView, latestCanObserve, LABEL)};
  });
  on('tool.call', {tool:'mcp__graph-skill-canvas__show_graph'}, async ($, e, next) => {
    if (typeof e.skill_root !== 'string' || !e.skill_root) return next(e);
    let available = false, projectRoot, nativeHost, unavailable = '';
    latestCanObserve = false;
    try {
      const tools = await $.tool.list();
      available = tools.some(tool => tool.name === PREVIEW_TOOL) && tools.some(tool => tool.name === NAVIGATE_TOOL);
      latestCanObserve = tools.some(tool => tool.name === CONTEXT_TOOL) && tools.some(tool => tool.name === SELECT_TOOL);
      if (available) {
        projectRoot = previewProjectRoot(await $.session.root());
        nativeHost = await readHostIdentity($);
        if (!nativeHost) throw new Error('Current Claude session identity is unavailable.');
      }
    }
    catch (error) { unavailable = 'Cannot identify the Claude preview project: ' + String(error.message || error); }
    const canPresent = available && projectRoot !== undefined && nativeHost !== undefined && nativeHost !== null;
    // Only the live host root can select the launch.json owner. Model-provided
    // roots must not redirect writes to another project when the API is absent.
    const {preview_project_root:ignoredRoot,presentation:requestedPresentation,native_host:ignoredIdentity,...graphInput} = e;
    const result = await next(canPresent ? {...graphInput,presentation:'html',preview_project_root:projectRoot,native_host:nativeHost} : graphInput);
    if (result.deny || result.isError || result.result?.isError) { latestView = null; return result; }
    try {
      latestView = null;
      if (!canPresent) throw new Error(unavailable || 'Claude preview_start and navigate tools are required to display the HTTP canvas.');
      const payload = graphPayload(result);
      latestView = previewTarget(payload,projectRoot);
      const bridge = bridgeDescriptor(payload);
      if (bridge) {
        state.bridges.set(bridgeKey(bridge),bridge);state.reported.delete(bridgeKey(bridge));
        // Claude emits session.end for /clear and /resume, without another
        // session.start. A new explicit graph display owns the new connection.
        if (state.closed) {
          state.closed = false;
          timer = $.clock.every(1000, async () => { await pollBridges($, state); });
        }
      }
      problem = '';
      // Keep graph data and the host's causal result reference intact.
      return {...result,context:[...(result.context || []),browserReminder(latestView, latestCanObserve, LABEL)]};
    } catch (error) {
      problem = 'Unable to show the graph: ' + String(error.message || error);
      $.ui.log(problem);
      return {...result,context:[...(result.context || []),problem + ' The graph result is preserved. Report this display limitation; do not use a static-file fallback or change permissions.']};
    }
  });
}
