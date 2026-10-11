import assert from "node:assert/strict";
import test from "node:test";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { z } from "zod";
import { McpAppTransport, MCP_APPS_PROTOCOL_VERSION } from "../adapters/codex/transport/index.mjs";

const nextTurn = () => new Promise(resolve => setImmediate(resolve));

function windows(origin = "https://codex.test") {
  const listeners = new Set();
  const outbound = [];
  const inbound = [];
  let receiveHost = () => {};
  const parent = { postMessage(message, targetOrigin) {
    outbound.push({ message, targetOrigin });
    queueMicrotask(() => receiveHost(message));
  } };
  const view = {
    parent,
    addEventListener(name, listener) { assert.equal(name, "message"); listeners.add(listener); },
    removeEventListener(name, listener) { assert.equal(name, "message"); listeners.delete(listener); },
  };
  const deliver = (data, source = parent, eventOrigin = origin) => {
    inbound.push(data);
    for (const listener of listeners) listener({ data, source, origin: eventOrigin });
  };
  const hostTransport = {
    async start() { receiveHost = message => hostTransport.onmessage?.(message); },
    async send(message) { queueMicrotask(() => deliver(message)); },
    async close() { receiveHost = () => {}; hostTransport.onclose?.(); },
  };
  return { view, outbound, inbound, deliver, hostTransport, listeners };
}

async function connected(t, options = {}) {
  const channel = windows(options.origin);
  const bridge = new AppBridge(null, { name: "Official test host", version: "1" }, {
    message: { text: {} }, updateModelContext: {}, serverTools: {},
    experimental: { "openai/files": {} },
  });
  const initialized = new Promise(resolve => { bridge.oninitialized = resolve; });
  await bridge.connect(channel.hostTransport);
  const app = new McpAppTransport({ name: "Canvas probe", version: "0" }, {}, {
    window: channel.view, timeoutMs: options.timeoutMs ?? 1_000,
  });
  t.after(async () => { await app.close(); await bridge.close(); });
  await app.connect();
  await initialized;
  return { app, bridge, ...channel };
}

test("compact transport completes the official AppBridge handshake and bidirectional operations", async t => {
  const { app, bridge, outbound } = await connected(t);
  assert.deepEqual(outbound[0].message.params, {
    appInfo: { name: "Canvas probe", version: "0" }, appCapabilities: {},
    protocolVersion: MCP_APPS_PROTOCOL_VERSION,
  });
  assert.equal(outbound[1].message.method, "ui/notifications/initialized");
  assert.equal(app.getHostVersion().name, "Official test host");
  assert.deepEqual(app.getHostCapabilities().experimental, { "openai/files": {} });
  const seen = [];
  bridge.onmessage = async params => { seen.push(params); return {}; };
  bridge.onupdatemodelcontext = async params => { seen.push(params); return {}; };
  bridge.oncalltool = async params => ({ content: [{ type: "text", text: params.name }] });
  bridge.setRequestHandler("openai/files/open", { params: z.object({ path: z.string() }) }, params => ({ opened: params.path }));
  assert.deepEqual(await app.sendMessage({ role: "user", content: [{ type: "text", text: "probe" }] }), {});
  assert.deepEqual(await app.updateModelContext({ content: [{ type: "text", text: "selected node" }] }), {});
  assert.equal((await app.callServerTool({ name: "canvas_probe", arguments: {} })).content[0].text, "canvas_probe");
  assert.deepEqual(await app.request({ method: "openai/files/open", params: { path: "C:/skill/SKILL.md" } }), { opened: "C:/skill/SKILL.md" });
  assert.equal(seen.length, 2);
  assert.equal(outbound.at(-1).targetOrigin, "https://codex.test");
  const received = new Promise(resolve => { app.ontoolresult = resolve; });
  await bridge.sendToolResult({ content: [], structuredContent: { skill_id: "real-input" } });
  assert.deepEqual((await received).structuredContent, { skill_id: "real-input" });
});

test("request correlation rejects alien sources and changed origins, retains host errors", async t => {
  const { app, bridge, deliver, outbound } = await connected(t);
  let release;
  bridge.oncalltool = () => new Promise(resolve => { release = resolve; });
  const result = app.callServerTool({ name: "pending" });
  const id = outbound.at(-1).message.id;
  deliver({ jsonrpc: "2.0", id, result: { forged: true } }, {});
  deliver({ jsonrpc: "2.0", id, result: { forged: true } }, app.parent, "https://other.test");
  deliver({ jsonrpc: "2.0", id: id + 99, result: { forged: true } });
  deliver({ jsonrpc: "2.0", id, result: null });
  deliver({ jsonrpc: "2.0", id, result: {}, error: { code: 0, message: "both" } });
  await nextTurn();
  assert.equal(app.pending.size, 1);
  release({ content: [{ type: "text", text: "correlated" }] });
  assert.equal((await result).content[0].text, "correlated");
  bridge.onmessage = async () => { throw new Error("Host denied this request"); };
  await assert.rejects(app.sendMessage({ role: "user", content: [{ type: "text", text: "probe" }] }), error => {
    assert.match(error.message, /Host denied/);
    assert.equal(error.outcome, "rejected");
    return true;
  });
});

test("opaque origins remain source-bound; teardown acknowledges and releases listeners", async t => {
  const { app, bridge, outbound, listeners } = await connected(t, { origin: "null" });
  bridge.onmessage = async () => ({});
  await app.sendMessage({ role: "user", content: [{ type: "text", text: "probe" }] });
  assert.equal(outbound.at(-1).targetOrigin, "*");
  await bridge.teardownResource({});
  assert.equal(app.state, "closed");
  assert.equal(listeners.size, 0);
  await assert.rejects(app.updateModelContext({}), { code: "HOST_UNAVAILABLE", outcome: "not-sent" });
});

test("timeout and disposal mean unknown action outcome and late responses cannot complete another request", async t => {
  const { app, bridge, deliver, outbound } = await connected(t, { timeoutMs: 15 });
  bridge.onmessage = () => new Promise(() => {});
  const timed = app.sendMessage({ role: "user", content: [{ type: "text", text: "probe" }] });
  const oldId = outbound.at(-1).message.id;
  await assert.rejects(timed, { code: "HOST_TIMEOUT", outcome: "unknown" });
  const pending = app.sendMessage({ role: "user", content: [{ type: "text", text: "next" }] });
  const rejected = assert.rejects(pending, { code: "HOST_CLOSED", outcome: "unknown" });
  deliver({ jsonrpc: "2.0", id: oldId, result: {} });
  assert.equal(app.pending.size, 1);
  await app.close();
  await rejected;
});

test("unsupported negotiated protocol fails closed before initialized notification", async () => {
  const channel = windows();
  channel.hostTransport.start();
  channel.hostTransport.onmessage = message => channel.deliver({ jsonrpc: "2.0", id: message.id, result: {
    protocolVersion: "2099-01-01", hostInfo: { name: "future", version: "1" }, hostCapabilities: {}, hostContext: {},
  } });
  const app = new McpAppTransport({ name: "probe", version: "1" }, {}, { window: channel.view });
  await assert.rejects(app.connect(), { code: "HOST_PROTOCOL" });
  assert.equal(channel.outbound.length, 1);
  assert.equal(channel.listeners.size, 0);
});
