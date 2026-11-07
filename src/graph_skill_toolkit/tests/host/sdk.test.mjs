import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { createMcpConnection, mcpConnection, mcpCapabilities } from "../../plugin_base/adapters/codex/connection/index.mjs";
import { codexAdapter } from "../../plugin_base/adapters/codex/driver/index.mjs";

function pair() {
  const left = {}, right = {};
  left.start = async () => {}; right.start = async () => {};
  left.send = async message => queueMicrotask(() => right.onmessage?.(message));
  right.send = async message => queueMicrotask(() => left.onmessage?.(message));
  left.close = async () => { left.onclose?.(); };
  right.close = async () => { right.onclose?.(); };
  return { left, right };
}

test("default iframe transport sends to its parent and completes the SDK handshake", async t => {
  const listeners = new Set(), peer = {};
  const parent = { postMessage: async data => queueMicrotask(() => peer.onmessage?.(data)) };
  const view = {
    parent, postMessage: () => assert.fail("The view must not send initialization to itself."),
    addEventListener: (name, callback) => { if (name === "message") listeners.add(callback); },
    removeEventListener: (name, callback) => { if (name === "message") listeners.delete(callback); },
  };
  peer.start = async () => {};
  peer.close = async () => peer.onclose?.();
  peer.send = async data => queueMicrotask(() => { for (const listener of listeners) listener({ source: parent, data }); });
  const oldWindow = globalThis.window;
  globalThis.window = view;
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, {});
  const connection = createMcpConnection({ window: view, appInfo: { name: "Plugin page", version: "0.0.0" } });
  t.after(async () => { await connection.dispose(); await bridge.close(); globalThis.window = oldWindow; });
  await bridge.connect(peer);
  await connection.connect({ receive() {}, fail: assert.fail });
  assert.equal((await connection.inspect()).identity.name, "chatgpt");
  assert.equal(listeners.size, 1);
});

test("official MCP Apps SDK establishes identity, capabilities and tool delivery", async t => {
  const { left, right } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, {
    message: { text: {} }, serverTools: {}, updateModelContext: { structuredContent: {} },
    experimental: { "openai/files": {}, "openai/message": { draft: {} } },
  });
  const app = new App({ name: "Graph Skill canvas", version: "0.3.5" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left, originatingServer: "graph-skill-canvas" });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  await bridge.connect(right);
  const received = [];
  await connection.connect({ receive: value => received.push(value), fail: assert.fail });
  const facts = await connection.inspect();
  assert.equal(facts.connected, true);
  assert.equal(facts.transport, "mcp-app");
  assert.equal(facts.identity.name, "chatgpt");
  assert.equal(facts.capabilities["tools.call"].state, "available");
  assert.equal(facts.capabilities["files.openFile"].state, "available");
  assert.equal(facts.capabilities["files.revealDirectory"].state, "unknown");
  assert.equal(facts.capabilities["composer.writeDraft"].state, "available");
  await bridge.sendToolResult({ content: [], structuredContent: { graph: { id: "changed" } } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(received[0].graph.id, "changed");
});

test("MCP capability interpretation does not infer unadvertised host operations", () => {
  const caps = mcpCapabilities({ message: { text: {} } });
  assert.equal(caps["conversation.submitMessage"].state, "available");
  assert.equal(caps["skills.invoke"].state, "available");
  assert.equal(caps["composer.writeDraft"].state, "unavailable");
  assert.equal(caps["tools.list"].state, "unavailable");
  for (const name of ["files.revealDirectory", "views.open"]) {
    assert.equal(caps[name].state, "unknown", name);
  }
});

test("Codex text and structured-context operations require their declared content modalities", () => {
  const caps = mcpCapabilities({
    message: { image: {} }, updateModelContext: { image: {} },
    experimental: { "openai/message": { draft: {} } },
  });
  for (const action of ["composer.writeDraft", "conversation.submitMessage", "skills.invoke", "context.update"]) {
    assert.equal(caps[action].state, "unavailable", action);
  }
});

test("MCP App lists its originating server tools through the SDK bridge", async t => {
  const { left, right } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, { serverTools: {} });
  const calls = [];
  bridge.oncalltool = async params => {
    calls.push(params);
    return { content: [], structuredContent: { scope: "originating-server", complete: true, tools: [{ name: "inspect_graph" }] } };
  };
  const app = new App({ name: "Graph Skill canvas", version: "0.3.5" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left, originatingServer: "graph-skill-canvas" });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  await bridge.connect(right);
  await connection.connect({ receive() {}, fail: assert.fail });
  const result = await codexAdapter(app, { originatingServer: "graph-skill-canvas" }).invoke("tools.list", {});
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data.tools.map(tool => tool.name), ["inspect_graph"]);
  assert.deepEqual(calls.map(({ name, arguments: args }) => ({ name, arguments: args })), [{ name: "list_page_tools", arguments: {} }]);
});

test("Codex delivers the startup path without using a host tool to read graph data", async t => {
  const { left, right } = pair();
  const root = "C:/selected/hello-world";
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, {});
  bridge.oncalltool = assert.fail;
  const app = new App({ name: "Graph Skill canvas", version: "0.3.5" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  await bridge.connect(right);
  const received = [], failed = [];
  await connection.connect({ receive: value => received.push(value), fail: error => failed.push(error) });
  await bridge.sendToolInput({ arguments: { skill_root: root } });
  for (let i = 0; i < 30 && received.length === 0; i++) await new Promise(resolve => setTimeout(resolve, 10));
  assert.deepEqual(received, [{ toolInput: { skill_root: root } }]);
  assert.deepEqual(failed, []);
});

test("Codex reports missing initial graph delivery instead of waiting forever", async t => {
  const { left, right } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, {});
  const app = new App({ name: "Graph Skill canvas", version: "0.3.5" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left, missingDataTimeoutMs: 1 });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  await bridge.connect(right);
  const failed = [];
  await connection.connect({ receive: assert.fail, fail: error => failed.push(error) });
  for (let i = 0; i < 30 && failed.length === 0; i++) await new Promise(resolve => setTimeout(resolve, 10));
  assert.match(failed[0]?.message ?? "", /没有向页面交付/);
});

test("Codex can receive the startup path from the result when the host omits input", async t => {
  const { left, right } = pair();
  const root = "C:/selected/hello-world";
  const bridge = new AppBridge(null, { name: "chatgpt", version: "3.2" }, {});
  bridge.oncalltool = assert.fail;
  const app = new App({ name: "Graph Skill canvas", version: "0.3.5" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  await bridge.connect(right);
  const received = [];
  await connection.connect({ receive: value => received.push(value), fail: assert.fail });
  await bridge.sendToolResult({ content: [], structuredContent: { skillRoot: root } });
  for (let i = 0; i < 30 && received.length === 0; i++) await new Promise(resolve => setTimeout(resolve, 10));
  assert.deepEqual(received, [{ skillRoot: root }]);
});
