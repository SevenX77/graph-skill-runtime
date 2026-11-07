import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { mcpConnection } from "../../../plugin_base/adapters/codex/connection/index.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { bridgeKey, createModState, pollBridges } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { contextText } from "../../../plugin_base/host_interfaces/context/update/index.mjs";
import { registerPluginBase } from "../../../plugin_base/adapters/claude/mod/hooks/base.js";

const action = "conversation.submitMessage";
function pair() {
  const left = { start: async () => {} }, right = { start: async () => {} };
  left.send = async value => queueMicrotask(() => right.onmessage?.(value));
  right.send = async value => queueMicrotask(() => left.onmessage?.(value));
  left.close = async () => left.onclose?.();
  right.close = async () => right.onclose?.();
  return { left, right };
}

test("message input is bounded text plus optional model and effort selections", () => {
  assert.deepEqual(validateArguments(action, { text: "  message  " }), { text: "  message  " });
  const full = { text: "m", model: { source: "specified", value: "claude-haiku-5-5" }, effort: { source: "specified", value: "low" } };
  assert.deepEqual(validateArguments(action, full), full);
  for (const args of [{ text: "m", model: { source: "default", value: "x" } }, { text: "m", effort: { source: "specified", value: "turbo" } }, { text: "m", model: { source: "auto" } }]) assert.throws(() => validateArguments(action, args));
  for (const args of [{ text: " " }, { text: "x".repeat(8001) }, { text: 2 }, { text: "yes", role: "assistant" }]) {
    assert.throws(() => validateArguments(action, args));
  }
});

test("Codex SDK sends one ui/message user-text request and distinguishes receipt from result", async t => {
  const { left, right } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, { message: { text: {} } });
  const app = new App({ name: "Graph Skill canvas", version: "0.3.5" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  const received = [];
  let reject = false;
  bridge.onmessage = async value => { received.push(value); return reject ? { isError: true } : {}; };
  await bridge.connect(right);
  await connection.connect({ receive() {}, fail: assert.fail });
  const driver = codexAdapter(app);
  assert.equal((await connection.inspect()).capabilities[action].state, "available");
  const result = await driver.invoke(action, { text: "please answer ✓" });
  assert.equal(result.status, "accepted");
  assert.match(result.message, /模型回复在对话中观察/);
  assert.deepEqual(result.evidence.sent, { role: "user", content: [{ type: "text", text: "please answer ✓" }] });
  assert.deepEqual(received, [{ role: "user", content: [{ type: "text", text: "please answer ✓" }] }]);
  reject = true;
  assert.equal((await driver.invoke(action, { text: "rejected" })).status, "error");
});

test("Codex unadvertised text is unavailable and an ambiguous reply is not called accepted", async () => {
  let calls = 0;
  const app = { getHostCapabilities: () => ({ message: { image: {} } }), sendMessage: async () => { calls++; return {}; } };
  assert.equal((await codexAdapter(app).invoke(action, { text: "do not send" })).status, "unsupported");
  assert.equal(calls, 0);
  app.getHostCapabilities = () => ({ message: { text: {} } });
  app.sendMessage = async () => { calls++; return null; };
  await assert.rejects(() => codexAdapter(app).invoke(action, { text: "unknown" }), /回执无法确认/);
  assert.equal(calls, 1);
});

test("Codex cannot select a model or effort and sends nothing when asked to", async () => {
  let calls = 0;
  const app = { getHostCapabilities: () => ({ message: { text: {} } }), sendMessage: async () => { calls++; return {}; } };
  for (const extra of [{ model: { source: "specified", value: "gpt-x" } }, { effort: { source: "default" } }]) {
    const result = await codexAdapter(app).invoke(action, { text: "hi", ...extra });
    assert.equal(result.status, "unsupported");
    assert.match(result.message, /没有模型和 effort 字段/);
  }
  assert.equal(calls, 0);
  assert.equal((await codexAdapter(app).invoke(action, { text: "hi", model: { source: "current" } })).status, "accepted");
  assert.equal(calls, 1);
});

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "C:/business/skill" };
const request = (id, text) => ({ id, action, args: { text }, key: bridge.key });
function claudeApi(submit, session = () => "session-a") {
  return { session: { id: async () => session(), model: async () => "claude-session-model" }, tool: { list: async () => [] }, prompt: { submit } };
}

test("Claude Mod inlines its page snapshot once and records inline delivery on an affirmative receipt", async () => {
  const state = createModState(), sends = [], owner = bridge.url + "/" + bridge.token;
  state.bridges.set(owner, bridge);
  state.contexts.set(owner, { snapshot: { node: { id: "one" } } });
  const api = claudeApi(async input => { sends.push(input); return { text: input.text, origin: {kind: "plugin", name: "graph-skill"} }; });
  const result = await executeBridgeAction(api, state, bridge, request("r1", "run"));
  assert.equal(result.status, "accepted");
  assert.deepEqual(result.data, { modified: false });
  const block = contextText({ node: { id: "one" } });
  assert.deepEqual(sends, [{ text: "run\n\n---\n" + block }]);
  assert.deepEqual(result.evidence.sent, { text: "run", inlinedContext: [block] });
  assert.equal(result.evidence.observed.contextDelivery, "inline");
  assert.deepEqual(state.events.map(e => [e.type, e.data.origin, e.data.blocks]), [["context.attached", "plugin-inline", [block]]]);
  assert.equal(result.evidence.observed.sessionModel, "claude-session-model");
  const other = { ...bridge, token: "b".repeat(64) };
  await executeBridgeAction(api, state, other, request("r2", "other"));
  assert.deepEqual(sends[1], { text: "other" });
});

test("Claude Mod reports hook rewrite or drop without pretending the requested text entered", async () => {
  const state = createModState();
  const modified = await executeBridgeAction(claudeApi(async () => ({ text: "rewritten" })), state, bridge, request("change", "original"));
  assert.equal(modified.status, "accepted");
  assert.equal(modified.data.modified, true);
  assert.match(modified.message, /改写/);
  const rejected = await executeBridgeAction(claudeApi(async () => ({ drop: "blocked by hook" })), state, bridge, request("drop", "original"));
  assert.deepEqual([rejected.status, rejected.message, rejected.data], ["rejected", "宿主拒绝消息提交。", { reason: "blocked by hook" }]);
});

test("Claude Mod lost receipt or changed session never triggers a second prompt submission", async () => {
  const state = createModState(); let count = 0;
  const api = claudeApi(async () => { count++; return {}; });
  await assert.rejects(() => executeBridgeAction(api, state, bridge, request("ambiguous", "hello")), /回执无法确认/);
  assert.equal(count, 1);
  let session = "session-a";
  const switched = claudeApi(async () => { count++; return { text: "hello" }; }, () => session);
  await assert.rejects(() => executeBridgeAction(switched, state, bridge, request("old", "hello"), { sessionId: "session-b" }), /原宿主会话/);
  assert.equal(count, 1);
});

test("Claude Mod keeps an unknown submission pending in the bridge and never replays it", async () => {
  const state = createModState(), results = [];
  state.bridges.set(bridgeKey(bridge), bridge);
  let sends = 0;
  const api = {
    session: { id: async () => "session-a", version: async () => ({version: "2.1.277"}), model: async () => "m" },
    tool: { list: async () => [] },
    prompt: { submit: async () => { sends++; return undefined; } },
    http: { fetch: async (url, options) => {
      if (url.endsWith("/poll")) return { ok: true, text: JSON.stringify({requests: [request("same-id", "hello")]}) };
      if (url.endsWith("/result")) results.push(JSON.parse(options.body));
      return { ok: true, text: "{}" };
    } },
  };
  await pollBridges(api, state);
  await new Promise(resolve => setImmediate(resolve));
  await pollBridges(api, state);
  assert.equal(sends, 1);
  assert.deepEqual(results.map(({ id, result }) => ({ id, status: result.status })), [{ id: "same-id", status: "pending" }]);
});

test("Claude applies a specified model and effort only to the turn its message started", async () => {
  const hooks = new Map();
  const on = (name, ...rest) => { if (rest.length === 1) hooks.set(name, rest[0]); };
  const state = registerPluginBase(on, { pages: [] });
  state.bridges.set(bridgeKey(bridge), bridge);
  const api = claudeApi(async input => ({ text: input.text }));
  const unsupported = await executeBridgeAction(api, state, bridge, { id: "d", action, args: { text: "x", model: { source: "default" } }, key: bridge.key });
  assert.equal(unsupported.status, "unsupported");
  state.contexts.set(bridgeKey(bridge), { snapshot: { node: "one" } });
  const result = await executeBridgeAction(api, state, bridge, { id: "s", action, args: { text: "use haiku", model: { source: "specified", value: "haiku" }, effort: { source: "specified", value: "low" } }, key: bridge.key });
  assert.equal(result.status, "accepted");
  assert.deepEqual(result.evidence.observed.turnOverride, { model: "haiku", effort: "low", turnId: null });
  await hooks.get("turn.start")({}, { text: "someone else", turnId: "t0" }, async e => ({ turnId: e.turnId }));
  // Claude Code 2.1.309 starts the turn of a plugin's prompt with the framed text the model reads.
  await hooks.get("turn.start")({}, { text: "The graph-skill-canvas-mod plugin sent a message:\n" + state.overrides[0].text, turnId: "t1" }, async e => ({ turnId: e.turnId }));
  assert.equal(state.overrides.length, 0);
  assert.equal(state.turns.get("t1").turnId, "t1");
  const seen = [];
  async function drive(turnId, agentId) {
    const stream = hooks.get("turn.step")({}, { turnId, index: 0, model: "opus", effort: "high", messageCount: 1, ...(agentId ? { agentId } : {}) },
      async function* (e) { seen.push([e.turnId, e.agentId ?? null, e.model, e.effort]); return { stop: "end" }; });
    while (!(await stream.next()).done);
  }
  await drive("t0"); await drive("t1"); await drive("t1", "sub");
  assert.deepEqual(seen, [["t0", null, "opus", "high"], ["t1", null, "haiku", "low"], ["t1", "sub", "opus", "high"]]);
  await hooks.get("turn.complete")({}, { turnId: "t1", reason: "answer", durationMs: 1, isAborted: false }, async () => ({ text: "done" }));
  const completed = state.events.find(event => event.type === "turn.completed");
  assert.deepEqual(completed.data.override.applied, { model: "haiku", effort: "low", sessionWouldUse: { model: "opus", effort: "high" } });
});
