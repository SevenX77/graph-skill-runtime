import { PREVIEW_TOOL, NAVIGATE_TOOL, CONTEXT_TOOL, SELECT_TOOL } from '../host_tools/index.mjs';
import { bridgeDescriptor, bridgeKey, bridgePost, readHostIdentity, pollBridges, flushEvents, queueEvent, createModState } from '../lifecycle/index.mjs';
import { previewProjectRoot, previewTarget, browserReminder } from '../../presentation/guidance/index.mjs';
import { contextText } from '../../../../host_interfaces/context/update/index.mjs';

// The Mod engine accepts $ only as a plain argument to declared functions, in
// call position, so every helper that touches the host is a function declaration.
function startPolling($, holder, state) {
  state.closed = false;
  if (holder.timer) holder.timer.cancel();
  holder.timer = $.clock.every(1000, async () => { await pollBridges($, state); });
}

async function endSession($, holder, state) {
  queueEvent(state, 'session.ended');
  await flushEvents($, state);
  state.closed = true;
  state.generation++;
  if (holder.timer) holder.timer.cancel();
  for (const bridge of state.bridges.values()) {
    try { await bridgePost($, bridge, '/disconnect', {}); } catch { /* The stdio owner also closes the bridge. */ }
  }
  state.bridges.clear();state.contexts.clear();state.views.clear();state.seen.clear();state.receipts.clear();state.running.clear();
  state.events.length = 0;state.overrides.length = 0;state.turns.clear();
}

async function presentationFacts($) {
  const tools = await $.tool.list();
  const available = tools.some(tool => tool.name === PREVIEW_TOOL) && tools.some(tool => tool.name === NAVIGATE_TOOL);
  const canObserve = tools.some(tool => tool.name === CONTEXT_TOOL) && tools.some(tool => tool.name === SELECT_TOOL);
  if (!available) return { available, canObserve };
  const projectRoot = previewProjectRoot(await $.session.root());
  const nativeHost = await readHostIdentity($);
  if (!nativeHost) throw new Error('Current Claude session identity is unavailable.');
  return { available, canObserve, projectRoot, nativeHost };
}

async function presentPage($, page, holder, state, e, next) {
  if (page.accepts && !page.accepts(e)) return next(e);
  const latest = holder.latest.get(page.tool) ?? {};
  holder.latest.set(page.tool, latest);
  let facts = { available: false, canObserve: false }, unavailable = '';
  try { facts = await presentationFacts($); }
  catch (error) { unavailable = 'Cannot identify the Claude preview project: ' + String(error.message || error); }
  latest.canObserve = facts.canObserve;
  const canPresent = facts.available && facts.projectRoot !== undefined && Boolean(facts.nativeHost);
  // Only the live host root selects the launch.json owner; model-provided
  // roots never redirect writes to another project.
  const {preview_project_root:ignoredRoot,presentation:ignoredPresentation,native_host:ignoredIdentity,...input} = e;
  const result = await next(canPresent ? {...input,presentation:'html',preview_project_root:facts.projectRoot,native_host:facts.nativeHost} : input);
  if (result.deny || result.isError || result.result?.isError) { latest.view = null; return result; }
  try {
    latest.view = null;
    if (!canPresent) throw new Error(unavailable || 'Claude preview_start and navigate tools are required to display the HTTP page.');
    const payload = page.readPayload(result);
    latest.view = previewTarget(payload, facts.projectRoot);
    const bridge = bridgeDescriptor(payload);
    if (bridge) {
      state.bridges.set(bridgeKey(bridge), bridge); state.reported.delete(bridgeKey(bridge));
      // Claude emits session.end for /clear and /resume without another
      // session.start; a new explicit presentation owns the new connection.
      if (state.closed) startPolling($, holder, state);
    }
    latest.problem = '';
    return {...result,context:[...(result.context || []),browserReminder(latest.view, latest.canObserve, page.label)]};
  } catch (error) {
    latest.problem = 'Unable to show ' + page.label + ': ' + String(error.message || error);
    $.ui.log(latest.problem);
    return {...result,context:[...(result.context || []),latest.problem + ' The tool result is preserved. Report this display limitation; do not use a static-file fallback or change permissions.']};
  }
}

/** Register the Plugin Base hooks once per Mod.
 * @param {(event: string, ...rest: any[]) => void} on
 * @param {{pages?: {tool: string, label: string, command?: {name: string, description: string}, accepts?: (input: any) => boolean, readPayload: (result: any) => any}[]}} [options]
 */
export function registerPluginBase(on, { pages = [] } = {}) {
  const state = createModState();
  const holder = { timer: null, latest: new Map() };
  on('session.start', async ($, e, next) => {
    startPolling($, holder, state);
    for (const page of pages) if (page.command) await $.command.register(page.command);
    return next(e);
  });
  on('session.end', async ($, e, next) => {
    await endSession($, holder, state);
    return next(e);
  });
  // context.update: this session's page snapshots ride along with the next
  // prompt from another sender, visible to the model and hidden from the user.
  // A failure in this bookkeeping never blocks the user's prompt.
  on('prompt.submit', async ($, e, next) => {
    if (e.origin?.kind === 'plugin' && e.origin.name === 'graph-skill-canvas-mod') return next(e);
    let blocks = [];
    try { blocks = [...state.contexts.values()].filter(item => item && Object.keys(item.snapshot).length).map(item => contextText(item.snapshot)); }
    catch { blocks = []; }
    if (!blocks.length) return next(e);
    const result = await next({...e,context:[...(e.context || []),...blocks]});
    try { queueEvent(state, 'context.attached', { blocks, attached: result?.context ?? null, origin: e.origin?.kind ?? null }); } catch { /* Event relay is best effort. */ }
    return result;
  });
  // conversation.submitMessage with a specified model or effort: bind the
  // turn its text started, then rewrite only that turn's main-loop requests.
  on('turn.start', async ($, e, next) => {
    const result = await next(e);
    const index = state.overrides.findIndex(item => item.text === e.text);
    if (index >= 0) { const [item] = state.overrides.splice(index, 1); item.turnId = e.turnId; state.turns.set(e.turnId, item); }
    return result;
  });
  on('turn.step', async function* ($, e, next) {
    const item = e.agentId ? undefined : state.turns.get(e.turnId);
    if (!item) return yield* next(e);
    item.applied = { model: item.model ?? e.model, effort: item.effort ?? e.effort ?? null, sessionWouldUse: { model: e.model, effort: e.effort ?? null } };
    return yield* next({...e, ...(item.model ? {model:item.model} : {}), ...(item.effort ? {effort:item.effort} : {})});
  });
  on('turn.complete', async ($, e, next) => {
    const result = await next(e);
    if (!e.agentId) {
      const item = state.turns.get(e.turnId);
      state.turns.delete(e.turnId);
      queueEvent(state, 'turn.completed', { turnId: e.turnId, reason: e.reason, model: e.usage?.model ?? null,
        override: item ? { requestId: item.requestId, requested: { model: item.model ?? null, effort: item.effort ?? null }, applied: item.applied ?? null } : null });
    }
    return result;
  });
  on('tool.call', async ($, e, next) => {
    const result = await next(e);
    try { queueEvent(state, 'tool.completed', { tool: e.tool ?? null, isError: Boolean(result?.isError || result?.result?.isError), denied: Boolean(result?.deny) }); } catch { /* Event relay is best effort. */ }
    return result;
  });
  for (const page of pages) {
    on('tool.call', {tool:page.tool}, async ($, e, next) => presentPage($, page, holder, state, e, next));
    if (page.command) on('command.run', {command:page.command.name}, async () => {
      const latest = holder.latest.get(page.tool);
      if (!latest?.view) return {text:latest?.problem || 'Nothing has been shown in this session yet.'};
      return {text:'[' + page.label + '](' + latest.view.url + ')\n' + browserReminder(latest.view, latest.canObserve, page.label)};
    });
  }
  return state;
}
