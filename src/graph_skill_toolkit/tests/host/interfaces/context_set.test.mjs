import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), skillRoot: "C:/skill" };
const request = (id, args) => ({ id, action: "context.set", args, skillRoot: bridge.skillRoot });

test("context.set requires an explicit portable JSON value and safe key", () => {
  for (const args of [{ key: "k" }, { key: "__proto__", content: 1 },
    { key: "k", content: undefined }, { key: "k", content: Number.NaN },
    { key: "k", content: { value: new Date() } }]) {
    assert.throws(() => validateArguments("context.set", args));
  }
  assert.deepEqual(validateArguments("context.set", { key: "k", content: null }), { key: "k", content: null });
});

test("Codex needs the declared structured-content modality and sends no message", async () => {
  const updates = [], messages = [];
  let features = { updateModelContext: { text: {} } };
  const app = { getHostCapabilities: () => features, getHostContext: () => ({}),
    updateModelContext: async value => { updates.push(value); return {}; },
    sendMessage: async value => { messages.push(value); return {}; } };
  const driver = codexAdapter(app);
  assert.equal((await driver.invoke("context.set", { key: "k", content: 1 })).status, "unsupported");
  assert.equal(updates.length, 0);
  features = { updateModelContext: { structuredContent: {} } };
  const result = await driver.invoke("context.set", { key: "k", content: { node: "α" } });
  assert.equal(result.status, "completed");
  assert.deepEqual(updates, [{ structuredContent: { toolkitContext: { k: { node: "α" } } } }]);
  assert.deepEqual(messages, []);
});

test("Codex serializes snapshots and does not commit a rejected update", async () => {
  const updates = [];
  let releaseFirst;
  const app = { getHostCapabilities: () => ({ updateModelContext: { structuredContent: {} } }), getHostContext: () => ({}),
    updateModelContext: async value => {
      updates.push(value);
      if (updates.length === 1) {
        await new Promise(resolve => { releaseFirst = resolve; });
        throw Object.assign(new Error("host rejected params"), { code: -32602 });
      }
      return {};
    } };
  const driver = codexAdapter(app);
  const first = driver.invoke("context.set", { key: "rejected", content: 1 });
  const second = driver.invoke("context.set", { key: "accepted", content: 2 });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(updates.length, 1);
  releaseFirst();
  await assert.rejects(first, error => error.outcome === "rejected");
  assert.equal((await second).status, "completed");
  assert.deepEqual(updates.map(value => value.structuredContent.toolkitContext), [
    { rejected: 1 }, { accepted: 2 },
  ]);
});

test("Codex unexpected isError reply cannot be treated as a safe rejection", async () => {
  const updates = [];
  const app = { getHostCapabilities: () => ({ updateModelContext: { structuredContent: {} } }),
    updateModelContext: async payload => { updates.push(payload.structuredContent.toolkitContext); return { isError: true }; } };
  const driver = codexAdapter(app);
  await assert.rejects(driver.invoke("context.set", { key: "old", content: 1 }), /效果不明/);
  assert.equal((await driver.invoke("context.set", { key: "new", content: 2 })).status, "rejected");
  assert.deepEqual(updates, [{ old: 1 }]);
});

test("Claude stores context for a later prompt without submitting or filling a draft", async () => {
  const state = createModState(), calls = [];
  const $ = { session: { id: async () => "session-a" }, tool: { list: async () => [] },
    prompt: { submit: async value => calls.push(["submit", value]), fill: async value => calls.push(["fill", value]) } };
  const args = { key: "selection", content: { node: "α" } };
  const result = await executeBridgeAction($, state, bridge, request("set-1", args));
  assert.equal(result.status, "completed");
  assert.deepEqual(calls, []);
  assert.deepEqual(Object.fromEntries(state.contexts.get(bridge.url + "/" + bridge.token).values),
    { selection: { node: "α" } });
  assert.equal(state.contexts.size, 1);
  const other = { ...bridge, token: "b".repeat(64) };
  await executeBridgeAction($, state, other, { ...request("set-2", { key: "other", content: false }) });
  assert.equal(state.contexts.size, 2);
  assert.deepEqual(calls, []);
  state.closed = true;
  await assert.rejects(executeBridgeAction($, state, bridge, request("stale", { key: "bad", content: 3 })), /已结束/);
  assert.equal(state.contexts.get(bridge.url + "/" + bridge.token).values.has("bad"), false);
});
