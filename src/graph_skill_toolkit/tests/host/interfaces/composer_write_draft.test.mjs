import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";

function pair() {
  const left = {}, right = {}, sent = [];
  left.start = async () => {}; right.start = async () => {};
  left.send = async message => { sent.push(message); queueMicrotask(() => right.onmessage?.(message)); };
  right.send = async message => queueMicrotask(() => left.onmessage?.(message));
  left.close = async () => left.onclose?.();
  right.close = async () => right.onclose?.();
  return { left, right, sent };
}

const draftCapabilities = { message: { text: {} }, experimental: { "openai/message": { draft: {} } } };

test("Codex sends a draft-only extension over the actual MCP Apps SDK wire", async t => {
  const { left, right, sent } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "test" }, draftCapabilities);
  const received = [];
  bridge.onmessage = async params => { received.push(params); return {}; };
  const app = new App({ name: "draft-test", version: "1" }, {}, { autoResize: false });
  t.after(async () => { await app.close(); await bridge.close(); });
  await bridge.connect(right);
  await app.connect(left);
  const result = await codexAdapter(app).invoke("composer.writeDraft", { text: "draft only", mode: "append" });
  assert.equal(result.status, "accepted");
  const messages = sent.filter(value => value.method === "ui/message");
  assert.equal(messages.length, 1);
  assert.deepEqual(messages[0].params, {
    role: "user", content: [{ type: "text", text: "draft only" }],
    _meta: { "openai/message": { target: "active", send: false } },
  });
  assert.equal(received.length, 1); // A simulated peer received a request, not proof of a real draft.
});

test("Codex refuses replace or missing draft declaration, and does not replay an unclear receipt", async () => {
  let declarations = draftCapabilities;
  const calls = [];
  const app = {
    getHostCapabilities: () => declarations,
    sendMessage: async params => { calls.push(params); return undefined; },
  };
  const adapter = codexAdapter(app);
  assert.equal((await adapter.invoke("composer.writeDraft", { text: "replace", mode: "replace" })).status, "unsupported");
  declarations = { message: { text: {} }, experimental: { "openai/message": {} } };
  assert.equal((await adapter.invoke("composer.writeDraft", { text: "missing", mode: "append" })).status, "unsupported");
  declarations = draftCapabilities;
  await assert.rejects(adapter.invoke("composer.writeDraft", { text: "once", mode: "append" }), /回执无法确认/);
  assert.equal(calls.length, 1);
});

test("Claude prompt.fill uses both draft modes without prompt.submit and distinguishes host refusal", async () => {
  const state = createModState(), fills = [];
  const root = "C:/business/skill";
  const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: root };
  let response = { isFilled: true, text: "draft", cursor: 5 };
  const $ = {
    session: { id: async () => "session-a" }, tool: { list: async () => [] },
    prompt: {
      fill: async input => { fills.push(input); return response; },
      submit: () => assert.fail("draft must not submit"),
    },
  };
  const request = (id, mode) => ({ id, action: "composer.writeDraft", args: { text: "draft", mode }, key: root });
  assert.equal((await executeBridgeAction($, state, bridge, request("one", "replace"))).status, "completed");
  assert.equal((await executeBridgeAction($, state, bridge, request("two", "append"))).status, "completed");
  assert.deepEqual(fills, [{ text: "draft", mode: "replace" }, { text: "draft", mode: "append" }]);
  response = { isFilled: false, text: "", cursor: 0 };
  assert.equal((await executeBridgeAction($, state, bridge, request("three", "append"))).status, "rejected");
  response = {};
  await assert.rejects(executeBridgeAction($, state, bridge, request("four", "append")), /回执无法确认/);
  assert.equal(fills.length, 4);
});
