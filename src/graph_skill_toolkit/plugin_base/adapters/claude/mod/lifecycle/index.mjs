import { executeBridgeAction, nativeCapabilities, sessionFacts } from '../operations/index.mjs';
export const bridgeKey = bridge => bridge.url + '/' + bridge.token;

export function bridgeDescriptor(payload) {
  const value = payload?.presentation?.bridge;
  if (!value) return null;
  if (typeof value.url !== 'string' || typeof value.token !== 'string' || typeof value.key !== 'string' || !value.key) throw new Error('Invalid page bridge descriptor.');
  const url = new URL(value.url);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/' || url.username || url.password || url.search || url.hash ||
      !/^[A-Za-z0-9_-]{32,256}$/.test(value.token)) throw new Error('Page bridge must use authenticated IPv4 loopback.');
  return { url:url.origin, token:value.token, key:value.key };
}

export async function readHostIdentity($) {
  try {
    const [sessionId, build] = await Promise.all([$.session.id(), $.session.version()]);
    if (typeof sessionId !== 'string' || !sessionId || typeof build?.version !== 'string' || !build.version) return null;
    return {name:'Claude Code',version:build.version,client_type:'claude_code',sessionId,source:'claude-mod-session'};
  } catch { return null; }
}

export async function bridgePost($, bridge, path, body) {
  const response = await $.http.fetch(bridge.url + path, {
    method:'POST',headers:{Authorization:'Bearer ' + bridge.token,'Content-Type':'application/json'},body:JSON.stringify(body),
  });
  if (!response.ok) throw Object.assign(new Error('Page bridge returned HTTP ' + response.status), { httpStatus: response.status });
  return JSON.parse(response.text);
}

async function executeAndReport($, state, bridge, request, sessionId) {
  const key = bridgeKey(bridge) + '/' + request.id;
  const generation = state.generation;
  let result;
  try {
    if (await $.session.id() !== sessionId || state.closed || state.generation !== generation) throw new Error('The originating Claude session has ended.');
    result = await executeBridgeAction($, state, bridge, request, { sessionId, generation });
  }
  catch (error) { result = {status:error.outcome === 'not-sent' ? 'error' : error.outcome === 'rejected' ? 'rejected' : 'pending',message:String(error.message || error), ...(error.data === undefined ? {} : { data: error.data })}; }
  state.running.delete(key);
  if (state.closed || state.generation !== generation) return;
  state.receipts.set(key, {bridge,id:request.id,result});
  await flushReceipts($, state);
}

async function flushReceipts($, state) {
  for (const [key, receipt] of state.receipts) {
    try {
      await bridgePost($, receipt.bridge, '/result', {id:receipt.id,result:receipt.result});
      state.receipts.delete(key);
    } catch { /* Retry the result, never the host operation, on the next poll. */ }
  }
}

/** Queue a host event for every page of this session; bounded so a closed page cannot grow it. */
export function queueEvent(state, type, data) {
  if (state.closed || !state.events || state.bridges.size === 0) return;
  state.events.push({ type, at: new Date().toISOString(), ...(data === undefined ? {} : { data }) });
  if (state.events.length > 200) state.events.splice(0, state.events.length - 200);
}

export async function flushEvents($, state) {
  if (!state.events?.length || state.bridges.size === 0) return;
  const events = state.events.splice(0);
  for (const bridge of state.bridges.values()) {
    try { await bridgePost($, bridge, '/events', { events }); } catch { /* A page that cannot receive events keeps its other functions. */ }
  }
}

export async function pollBridges($, state) {
  if (state.polling || state.closed || state.bridges.size === 0) return;
  const generation = state.generation;
  state.polling = true;
  try {
    await flushReceipts($, state);
    await flushEvents($, state);
    const tools = await $.tool.list();
    if (state.closed || state.generation !== generation) return;
    const identity = await readHostIdentity($);
    const capabilities = nativeCapabilities(tools, await sessionFacts($, state, identity?.sessionId ?? null));
    if (state.closed || state.generation !== generation) return;
    for (const bridge of state.bridges.values()) {
      try {
        const result = await bridgePost($, bridge, '/poll', {identity,capabilities});
        // A response may already be in flight when /clear ends the session.
        // Never dispatch that earlier session's actions after its boundary.
        if (state.closed || state.generation !== generation) return;
        if (!identity) continue;
        if (!Array.isArray(result.requests)) throw new Error('Page bridge returned no request list.');
        for (const request of result.requests) {
          const key = bridgeKey(bridge) + '/' + request.id;
          if (state.running.has(key) || state.seen.has(key)) continue;
          state.seen.add(key);state.running.add(key);
          // prompt.submit may wait for the active turn to finish. Its promise
          // must not block this worker's heartbeat or another read-only action.
          void executeAndReport($, state, bridge, request, identity.sessionId);
        }
      } catch (error) {
        if ([401,403,404].includes(error.httpStatus)) { state.bridges.delete(bridgeKey(bridge));state.contexts.delete(bridgeKey(bridge));state.views.delete(bridgeKey(bridge)); }
        if (!state.reported.has(bridgeKey(bridge))) { $.ui.log('Plugin page host connection unavailable: ' + String(error.message || error)); state.reported.add(bridgeKey(bridge)); }
      }
    }
  } finally { state.polling = false; }
}


export function createModState() {
  return { bridges: new Map(), running: new Set(), seen: new Set(), receipts: new Map(), reported: new Set(), contexts: new Map(), views: new Map(), viewQueues: new Map(), nextViewId: 0, sessionFacts: null, polling: false, closed: false, generation: 0,
    events: [], overrides: [], turns: new Map() };
}

