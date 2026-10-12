import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { createHostAdapter } from "../adapters/index.mjs";
import { HOST_ACTIONS } from "../ports/host/contract.mjs";
import { graph } from "../demo/graph.mjs";
import { createHostBridge } from "../adapters/claude/bridge/server.mjs";
import { pollBridges } from "../adapters/claude/mod/hooks/register.js";
import { launchHostInfo } from "../adapters/launch/index.mjs";

const payload = { skillRoot: "/business/skill", graph: { ...graph, width: 352, height: 548 } };
const capabilities = () => Object.fromEntries(HOST_ACTIONS.map(action => [action, { available: true, detail: action }]));
const callbacks = { receive() {}, fail: assert.fail };
function environment(snapshot = null, framed = true) {
  const window = { location: { origin: "http://127.0.0.1:12345" } };
  window.parent = framed ? {} : window;
  if (framed || snapshot) snapshot = {hostInfo:launchHostInfo({presentation:snapshot?.hostBridge !== undefined ? "html" : "mcp-app"}),...snapshot};
  return { window, document: { querySelector: () => ({ textContent: JSON.stringify(snapshot) }) } };
}
function fakeDriver(snapshot = payload, host = "codex") {
  const calls = [];
  return {
    calls, closes: 0,
    async inspect() { return {transport:host === "codex" ? "mcp-app" : "http-bridge",connected:true,identity:host === "codex" ? {name:"chatgpt",version:"test",client_type:"codex_desktop"} : {name:"Claude Code",version:"test",client_type:"claude_code",sessionId:"test-session",source:"claude-mod-session"},capabilities:await this.capabilities()}; },
    async connect(callbacks) { this.callbacks = callbacks; callbacks.receive(snapshot); },
    async capabilities() { return capabilities(); },
    async invoke(action, args) { calls.push({ action, args }); return { status: "accepted", message: action }; },
    async getResult(id) { calls.push({ receipt: id }); return { status: "completed", message: "read receipt", requestId: id }; },
    dispose() { this.closes++; },
  };
}
function argsFor(action, snapshot = payload) {
  return { skillRoot: snapshot.skillRoot,
    ...(["fill-prompt", "send-prompt"].includes(action) ? { text: "explicit button text" } : {}),
    ...(action === "update-context" ? { context: { skillRoot: snapshot.skillRoot, graphId: snapshot.graph.id, nodeId: snapshot.graph.nodes[0].id } } : {}),
  };
}
const facade = driver => createHostAdapter({ ...environment(), connections: {"mcp-app": () => driver}, drivers: { codex: () => driver, claude: assert.fail } });

test("the public entry detects both deliveries and routes every action to only their page owner", async () => {
  for (const hostId of ["claude", "codex"]) {
    const driver = fakeDriver(payload, hostId);
    const adapter = createHostAdapter({ ...environment(hostId === "claude" ? { ...payload, hostBridge: {} } : null),
      connections: {[hostId === "claude" ? "http-bridge" : "mcp-app"]: () => driver},
      drivers: { [hostId]: () => driver, [hostId === "claude" ? "codex" : "claude"]: assert.fail } });
    assert.equal(adapter.hostId, "unknown");
    assert.equal(adapter.state, "new");
    assert.equal((await adapter.invoke("open-root", argsFor("open-root"))).status, "error");
    await adapter.connect(callbacks);
    assert.equal(adapter.state, "connected");
    assert.equal(adapter.hostId, hostId);
    assert.deepEqual(await adapter.capabilities(), capabilities());
    for (const action of HOST_ACTIONS) assert.equal((await adapter.invoke(action, argsFor(action))).status, "accepted");
    assert.deepEqual(driver.calls, HOST_ACTIONS.map(action => ({ action, args: argsFor(action) })));
    assert.equal((await adapter.getResult("one")).status, "completed");
    await adapter.dispose(); await adapter.dispose();
    assert.equal(driver.closes, 1);
    assert.equal(adapter.state, "disposed");
    assert.equal((await adapter.invoke("open-root", argsFor("open-root"))).status, "error");
    assert.equal(driver.calls.length, 9);
    await assert.rejects(adapter.connect(callbacks));
  }
});

test("standalone pages stay a demo; malformed host data fails without guessing or switching hosts", async () => {
  assert.equal(createHostAdapter(environment(null, false)), null);
  for (const text of ["", "{bad", "123", JSON.stringify(payload)]) {
    const options = environment(); options.document.querySelector = () => ({ textContent: text });
    const adapter = createHostAdapter({ ...options, drivers: { claude: assert.fail, codex: assert.fail } });
    assert.equal(adapter.hostId, "unknown");
    await assert.rejects(adapter.connect(callbacks));
    assert.equal(adapter.state, "failed");
  }
  const driver = fakeDriver(); driver.connect = async () => { throw new Error("failed handshake"); };
  const adapter = facade(driver);
  await assert.rejects(adapter.connect(callbacks), /handshake/);
  assert.equal(driver.closes, 1);
  assert.equal((await adapter.invoke("send-prompt", argsFor("send-prompt"))).status, "error");
  assert.equal(driver.calls.length, 0);
  for (const hostBridge of [null, {}, { url: "https://foreign.invalid", token: "a".repeat(48) }, { url: "http://127.0.0.1:12346", token: "a".repeat(48) }]) {
    const invalid = createHostAdapter({ ...environment({ ...payload, hostBridge }), drivers: { codex: assert.fail } });
    await assert.rejects(invalid.connect({ receive: assert.fail, fail() {} }));
    assert.equal(invalid.state, "failed");
  }
});

test("unavailable, invalid and cross-root requests are stopped before host execution", async () => {
  const driver = fakeDriver(), adapter = facade(driver);
  await adapter.connect(callbacks);
  for (const [action, args] of [
    ["open-root", { skillRoot: "/other" }], ["open-root", { skillRoot: payload.skillRoot, command: "anything" }],
    ["send-prompt", { skillRoot: payload.skillRoot, text: " " }],
    ["update-context", { skillRoot: payload.skillRoot, context: { skillRoot: payload.skillRoot, graphId: "wrong" } }],
    ["update-context", { skillRoot: payload.skillRoot, context: { skillRoot: payload.skillRoot, graphId: graph.id, nodeId: "missing" } }],
  ]) assert.equal((await adapter.invoke(action, args)).status, "error");
  assert.equal((await adapter.invoke("shell", argsFor("open-root"))).status, "unsupported");
  driver.capabilities = async () => ({});
  assert.equal((await adapter.invoke("open-file", argsFor("open-file"))).status, "unsupported");
  driver.capabilities = async () => ({ "open-file": { available: "yes", detail: "invalid" } });
  assert.equal((await adapter.invoke("open-file", argsFor("open-file"))).status, "unsupported");
  assert.equal(adapter.hostId, "unknown");
  assert.equal(driver.calls.length, 0);
  await adapter.dispose();
});

test("graph updates and disposal while reading capabilities cancel dispatch; caller mutation cannot change captured input", async () => {
  const driver = fakeDriver(), adapter = facade(driver);
  await adapter.connect(callbacks);
  let resolveCaps;
  driver.capabilities = () => new Promise(resolve => { resolveCaps = resolve; });
  const changed = adapter.invoke("open-file", argsFor("open-file"));
  driver.callbacks.receive({ ...payload, graph: { ...payload.graph, id: "updated" } });
  resolveCaps(capabilities());
  assert.equal((await changed).status, "rejected");
  const args = argsFor("send-prompt"), captured = adapter.invoke("send-prompt", args);
  args.skillRoot = "/other"; args.text = "replaced";
  resolveCaps(capabilities()); await captured;
  assert.deepEqual(driver.calls, [{ action: "send-prompt", args: argsFor("send-prompt") }]);
  const closed = adapter.invoke("open-file", argsFor("open-file"));
  await adapter.dispose(); resolveCaps(capabilities());
  assert.equal((await closed).status, "error");
  assert.equal(driver.calls.length, 1);
});

test("dispose during connection closes once and suppresses all late graph callbacks", async () => {
  const driver = fakeDriver(), received = [];
  let finish, graphCallbacks;
  driver.connect = value => { graphCallbacks = value; return new Promise(resolve => { finish = resolve; }); };
  const adapter = facade(driver), connection = adapter.connect({ receive: value => received.push(value), fail: assert.fail });
  await adapter.dispose();
  graphCallbacks.receive(payload); finish();
  await assert.rejects(connection, /关闭/);
  assert.deepEqual(received, []); assert.equal(driver.closes, 1); assert.equal(adapter.state, "disposed");
});

test("unknown effects, malformed results and closed in-flight actions stay pending without retry", async () => {
  for (const outcome of ["unknown", "malformed", "closed", "rejected", "not-sent"]) {
    const driver = fakeDriver();
    const adapter = facade(driver); await adapter.connect(callbacks);
    let sent = 0;
    driver.invoke = async () => {
      sent++;
      if (outcome === "malformed") return { status: "invented-success", requestId: "uncertain" };
      if (outcome === "closed") { await adapter.dispose(); return { status: "accepted", message: "accepted", requestId: "in-flight" }; }
      throw Object.assign(new Error("transport outcome"), { outcome, requestId: "uncertain" });
    };
    const result = await adapter.invoke("send-prompt", argsFor("send-prompt"));
    assert.equal(result.status, outcome === "rejected" ? "rejected" : outcome === "not-sent" ? "error" : "pending");
    assert.equal(sent, 1);
    if (["unknown", "malformed"].includes(outcome)) assert.equal(result.requestId, "uncertain");
    await adapter.dispose();
  }
});

test("two page factories keep their roots, graph callbacks and receipts isolated", async () => {
  const other = { ...payload, skillRoot: "/business/other" }, a = fakeDriver(), b = fakeDriver(other);
  const first = facade(a), second = facade(b);
  await first.connect(callbacks); await second.connect(callbacks);
  assert.equal((await first.invoke("open-file", { skillRoot: other.skillRoot })).status, "error");
  await second.invoke("open-file", { skillRoot: other.skillRoot });
  await first.dispose();
  await second.invoke("send-prompt", argsFor("send-prompt", other));
  assert.equal(a.calls.length, 0); assert.equal(b.calls.length, 2); assert.equal(second.state, "connected");
  await second.dispose();
});

test("invalid graph updates clear action authority and consumer mutations cannot change the bound root", async () => {
  const driver = fakeDriver(), adapter = facade(driver), failures = [];
  await adapter.connect({ receive: value => { value.skillRoot = "/mutated-by-consumer"; }, fail: error => failures.push(error) });
  assert.equal((await adapter.invoke("open-file", argsFor("open-file"))).status, "accepted");
  driver.callbacks.receive({ ...payload, graph: { ...payload.graph, nodes: [] } });
  assert.equal(failures.length, 1);
  assert.equal((await adapter.invoke("open-file", argsFor("open-file"))).status, "error");
  driver.callbacks.receive(payload);
  assert.equal((await adapter.invoke("open-file", argsFor("open-file"))).status, "accepted");
  assert.equal(driver.calls.length, 2);
  await adapter.dispose();
});

test("public automatic Claude path reaches the real authenticated HTTP bridge and Mod operation executor", async t => {
  const owner = createHostBridge({ responseWaitMs: 10 });
  t.after(() => owner.close());
  const view = await owner.createView(payload.skillRoot), calls = [];
  let receiptPosted;
  const state = { bridges: new Map([[view.mod.url, { ...view.mod, skillRoot: payload.skillRoot }]]),
    running: new Set(), seen: new Set(), receipts: new Map(), reported: new Set(), context: null, polling: false, closed: false, generation: 0 };
  const api = { session: {id:async()=>"public-entry-session",version:async()=>({version:"test-engine"})}, prompt: { fill: async args => { calls.push({ fill: args }); return { isFilled: true }; },
    submit: async args => { calls.push({ submit: args }); return { text: args.text }; } },
    tool: { list: async () => [{ name: "mcp__graph-skill-canvas__inspect_graph" }] }, ui: { log: assert.fail },
    http: { fetch: async (url, init) => {
      const response = await fetch(url, init), result = { ok: response.ok, status: response.status, text: await response.text() };
      if (url.endsWith("/result")) receiptPosted();
      return result;
    } } };
  await pollBridges(api, state);
  const env = environment({ ...payload, hostBridge: view.browser }); env.window.location.origin = new URL(view.browser.url).origin;
  const adapter = createHostAdapter(env); t.after(() => adapter.dispose());
  await adapter.connect(callbacks); assert.equal(adapter.hostId, "claude");
  for (const action of HOST_ACTIONS) {
    const receipt = await adapter.invoke(action, argsFor(action));
    assert.equal(receipt.status, "pending", action);
    const posted = new Promise(resolve => { receiptPosted = resolve; });
    await pollBridges(api, state); await posted;
    const result = await adapter.getResult(receipt.requestId);
    assert.equal(result.status, ["fill-prompt", "update-context", "list-tools"].includes(action) ? "completed" : "accepted", action);
  }
  assert.equal(calls.filter(call => call.fill).length, 1);
  assert.equal(calls.filter(call => call.submit).length, 5);
  assert.equal(state.context.nodeId, graph.nodes[0].id);
  await pollBridges(api, state); assert.equal(calls.length, 6);
});

test("public automatic MCP path negotiates the parent protocol before dispatching actual request shapes", async () => {
  const env = environment(), listeners = new Set(), sent = [];
  const deliver = data => { for (const listener of listeners) listener({ source: env.window.parent, origin: "https://test-host.invalid", data }); };
  env.window.addEventListener = (_name, listener) => listeners.add(listener);
  env.window.removeEventListener = (_name, listener) => listeners.delete(listener);
  env.window.parent.postMessage = message => {
    sent.push(message);
    if (message.id === undefined) return;
    queueMicrotask(() => deliver({ jsonrpc: "2.0", id: message.id, result: message.method === "ui/initialize" ? {
      protocolVersion: "2026-01-26", hostInfo: { name: "chatgpt", version: "1", client_type: "codex_desktop" }, hostContext: {},
      hostCapabilities: { message: {}, serverTools: {}, updateModelContext: {}, experimental: { "openai/files": {}, "openai/message": { draft: {} } } },
    } : message.method === "tools/call" ? { structuredContent: payload } : {} }));
  };
  const adapter = createHostAdapter(env);
  assert.equal(sent.length, 0); await adapter.connect(callbacks);
  deliver({ jsonrpc: "2.0", method: "ui/notifications/tool-result", params: { structuredContent: payload } });
  for (const action of HOST_ACTIONS) {
    const response = await adapter.invoke(action, argsFor(action));
    assert.equal(response.status, action === "list-tools" ? "unsupported" : ["update-context", "call-tool"].includes(action) ? "completed" : "accepted");
  }
  assert.deepEqual(sent.filter(item => item.id !== undefined).map(item => item.method), [
    "ui/initialize", "ui/message", "openai/files/open", "ui/message", "ui/message", "ui/update-model-context", "tools/call", "ui/message",
  ]);
  assert.equal(sent.find(item => item.method === "tools/call").params.name, "inspect_graph");
  assert.equal(adapter.getResult, undefined);
  await adapter.dispose(); assert.equal(listeners.size, 0);
});

test("the application imports only the public adapter entry and shared UI has no provider branch", async () => {
  const entry = await readFile(new URL("../app/main.tsx", import.meta.url), "utf8");
  const ui = await readFile(new URL("../ui/workbench/index.tsx", import.meta.url), "utf8");
  assert.match(entry, /createHostAdapter\(\)/);
  assert.doesNotMatch(entry + ui, /adapters\/(?:codex|claude)|window\.parent|graph-skill-snapshot|isClaude|isCodex|openRoot/);
});
