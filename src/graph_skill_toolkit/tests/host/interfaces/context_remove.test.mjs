import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";

function pair() {
  const view = { start: async () => {}, close: async () => {}, send: async message => queueMicrotask(() => host.onmessage?.(message)) };
  const host = { start: async () => {}, close: async () => {}, send: async message => queueMicrotask(() => view.onmessage?.(message)) };
  return { view, host };
}

test("Codex sends the remaining complete page context through the SDK protocol without a message", async t => {
  const { view, host } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, { updateModelContext: { structuredContent: {} } });
  const app = new App({ name: "canvas", version: "0.3.5" }, {}, { autoResize: false });
  const updates = [];
  bridge.onupdatemodelcontext = async params => { updates.push(params); return {}; };
  t.after(async () => { await app.close(); await bridge.close(); });
  await bridge.connect(host);
  await app.connect(view);
  const adapter = codexAdapter(app);
  assert.equal((await adapter.invoke("context.set", { key: "alpha", content: { node: "start" } })).status, "completed");
  assert.equal((await adapter.invoke("context.set", { key: "beta", content: 2 })).status, "completed");
  const result = await adapter.invoke("context.remove", { key: "alpha" });
  assert.equal(result.status, "completed");
  assert.equal(result.data.scope, "page-connection");
  assert.deepEqual(updates, [
    { structuredContent: { toolkitContext: { alpha: { node: "start" } } } },
    { structuredContent: { toolkitContext: { alpha: { node: "start" }, beta: 2 } } },
    { structuredContent: { toolkitContext: { beta: 2 } } },
  ]);
  assert.equal((await adapter.invoke("context.remove", { key: "beta" })).status, "completed");
  assert.deepEqual(updates.at(-1), { structuredContent: { toolkitContext: {} } });
});

test("Codex refuses unadvertised context updates and does not dispatch a host request", async () => {
  let sent = 0;
  const app = { getHostCapabilities: () => ({ updateModelContext: { text: {} } }), updateModelContext: async () => { sent++; } };
  const result = await codexAdapter(app).invoke("context.remove", { key: "alpha" });
  assert.equal(result.status, "unsupported");
  assert.equal(sent, 0);
});

test("Claude removes only the current page owner's key before a later submit", async () => {
  const state = createModState(), messages = [];
  const api = {
    session: { id: async () => "session-a" }, tool: { list: async () => [] },
    prompt: { submit: async input => { messages.push(input); return { text: input.text }; } },
  };
  const bridge = token => ({ url: "http://127.0.0.1:12345", token, key: "C:/skill" });
  const a = bridge("a".repeat(64)), b = bridge("b".repeat(64));
  const action = (id, name, args) => ({ id, action: name, args, key: "C:/skill" });
  const run = (owner, id, name, args) => executeBridgeAction(api, state, owner, action(id, name, args));
  await run(a, "set-a", "context.set", { key: "selection", content: "first" });
  await run(b, "set-b", "context.set", { key: "selection", content: "second" });
  const removed = await run(a, "remove-a", "context.remove", { key: "selection" });
  assert.equal(removed.status, "completed");
  assert.equal(removed.data.scope, "page-connection");
  assert.equal(messages.length, 0);
  assert.equal((await run(a, "send-a", "conversation.submitMessage", { text: "later" })).status, "accepted");
  assert.equal((await run(b, "send-b", "conversation.submitMessage", { text: "later" })).status, "accepted");
  assert.equal(messages[0].text, "later");
  assert.match(messages[1].text, /"selection":"second"/);
});

test("context.remove rejects prototype keys, unknown fields and missing keys at the boundary", () => {
  for (const args of [{ key: "__proto__" }, { key: "constructor" }, { key: "prototype" }, { key: "ordinary", extra: true }, {}]) {
    assert.throws(() => validateArguments("context.remove", args));
  }
  assert.deepEqual(validateArguments("context.remove", { key: "ordinary" }), { key: "ordinary" });
});
