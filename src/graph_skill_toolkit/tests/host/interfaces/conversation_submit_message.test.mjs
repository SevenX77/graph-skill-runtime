import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { mcpConnection } from "../../../plugin_base/adapters/codex/connection/index.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { bridgeKey, createModState, pollBridges } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";

const action = "conversation.submitMessage";
function pair() {
  const left = { start: async () => {} }, right = { start: async () => {} };
  left.send = async value => queueMicrotask(() => right.onmessage?.(value));
  right.send = async value => queueMicrotask(() => left.onmessage?.(value));
  left.close = async () => left.onclose?.();
  right.close = async () => right.onclose?.();
  return { left, right };
}

test("message input is a bounded, nonempty single text field", () => {
  assert.deepEqual(validateArguments(action, { text: "  message  " }), { text: "  message  " });
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
  assert.match(result.message, /实际会话效果需观察/);
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

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "C:/business/skill" };
const request = (id, text) => ({ id, action, args: { text }, key: bridge.key });
function claudeApi(submit, session = () => "session-a") {
  return { session: { id: async () => session() }, tool: { list: async () => [] }, prompt: { submit } };
}

test("Claude Mod submits page-owned text once, and accepts only an affirmative prompt.submit receipt", async () => {
  const state = createModState(), sends = [], owner = bridge.url + "/" + bridge.token;
  state.contexts.set(owner, { scope: "selection", values: new Map([["node", { id: "one" }]]) });
  const api = claudeApi(async input => { sends.push(input); return { text: input.text, origin: {kind: "plugin", name: "graph-skill"} }; });
  const result = await executeBridgeAction(api, state, bridge, request("r1", "run"));
  assert.equal(result.status, "accepted");
  assert.deepEqual(result.data, { modified: false });
  assert.deepEqual(sends, [{ text: 'run\n\nToolkit context supplied as data: {"node":{"id":"one"}}' }]);
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
  assert.deepEqual(rejected, { status: "rejected", message: "宿主拒绝消息提交。", data: { reason: "blocked by hook" } });
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
    session: { id: async () => "session-a", version: async () => ({version: "2.1.277"}) },
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
