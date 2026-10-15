import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { createModState, bridgeKey } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { registerPluginBase } from "../../../plugin_base/adapters/claude/mod/hooks/base.js";
import { contextText } from "../../../plugin_base/host_interfaces/context/update/index.mjs";

const action = "context.update";
const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "page-a" };
const request = (id, snapshot, from = bridge) => ({ id, action, args: { snapshot }, key: from.key });

test("context.update takes one portable JSON object snapshot", () => {
  assert.deepEqual(validateArguments(action, { snapshot: { node: "α" } }), { snapshot: { node: "α" } });
  assert.deepEqual(validateArguments(action, { snapshot: {} }), { snapshot: {} });
  for (const args of [{}, { snapshot: [] }, { snapshot: "text" }, { snapshot: { when: new Date() } }, { snapshot: {}, key: "k" }]) {
    assert.throws(() => validateArguments(action, args));
  }
});

test("Codex replaces the whole snapshot in the declared modalities and sends no message", async () => {
  const updates = [], messages = [];
  const app = { getHostCapabilities: () => ({ updateModelContext: { text: {}, structuredContent: {} } }), getHostContext: () => ({}),
    updateModelContext: async value => { updates.push(value); return {}; }, sendMessage: async value => { messages.push(value); return {}; } };
  const driver = codexAdapter(app);
  const first = await driver.invoke(action, { snapshot: { node: "α" } });
  assert.equal(first.status, "completed");
  assert.deepEqual(first.evidence.sent, { content: [{ type: "text", text: contextText({ node: "α" }) }], structuredContent: { node: "α" } });
  assert.equal((await driver.invoke(action, { snapshot: {} })).data.cleared, true);
  assert.deepEqual(updates, [first.evidence.sent, { content: [] }]);
  assert.deepEqual(messages, []);
});

test("Codex without a declared context modality is unavailable and sends nothing", async () => {
  const updates = [];
  const app = { getHostCapabilities: () => ({ updateModelContext: { image: {} } }), getHostContext: () => ({}), updateModelContext: async value => { updates.push(value); return {}; } };
  assert.equal((await codexAdapter(app).invoke(action, { snapshot: { a: 1 } })).status, "unsupported");
  assert.deepEqual(updates, []);
});

test("Codex treats a malformed receipt as an unknown effect, never as success", async () => {
  const app = { getHostCapabilities: () => ({ updateModelContext: { structuredContent: {} } }), getHostContext: () => ({}), updateModelContext: async () => ({ isError: true }) };
  await assert.rejects(codexAdapter(app).invoke(action, { snapshot: { a: 1 } }), /回执不明/);
});

test("Claude stores one snapshot per page without submitting or filling a draft", async () => {
  const state = createModState(), calls = [];
  const $ = { session: { id: async () => "session-a" }, tool: { list: async () => [] },
    prompt: { submit: async value => calls.push(["submit", value]), fill: async value => calls.push(["fill", value]) } };
  const result = await executeBridgeAction($, state, bridge, request("u1", { node: "α" }));
  assert.equal(result.status, "completed");
  assert.equal(result.evidence.sent.attachAs, contextText({ node: "α" }));
  assert.deepEqual(state.contexts.get(bridgeKey(bridge)), { snapshot: { node: "α" } });
  const other = { ...bridge, token: "b".repeat(64), key: "page-b" };
  await executeBridgeAction($, state, other, request("u2", { flag: false }, other));
  assert.equal(state.contexts.size, 2);
  await executeBridgeAction($, state, bridge, request("u3", {}));
  assert.equal(state.contexts.has(bridgeKey(bridge)), false);
  assert.deepEqual(calls, []);
});

test("Claude attaches this session's snapshots to the next prompt from any sender and reports them", async () => {
  const hooks = new Map();
  const on = (name, ...rest) => { const handler = rest.at(-1); if (rest.length === 1) hooks.set(name, handler); };
  const state = registerPluginBase(on, { pages: [] });
  state.contexts.set("owner", { snapshot: { node: "α" } });
  let entered;
  const result = await hooks.get("prompt.submit")({}, { text: "change this node", origin: { kind: "composer" } }, async e => { entered = e; return { text: e.text, context: e.context }; });
  assert.deepEqual(entered.context, [contextText({ node: "α" })]);
  assert.deepEqual(result.context, [contextText({ node: "α" })]);
  assert.deepEqual(state.events.map(event => [event.type, event.data.blocks, event.data.origin]), [["context.attached", [contextText({ node: "α" })], "composer"]]);
  state.contexts.clear();
  const plain = await hooks.get("prompt.submit")({}, { text: "unrelated", origin: { kind: "composer" } }, async e => ({ text: e.text, context: e.context }));
  assert.equal(plain.context, undefined);
  assert.equal(state.events.length, 1);
});
