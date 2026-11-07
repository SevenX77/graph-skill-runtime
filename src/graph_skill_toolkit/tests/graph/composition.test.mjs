import assert from "node:assert/strict";
import { test } from "node:test";
import { createCanvasComposition } from "../../apps/graph_canvas/app/composition.mjs";

const hostInfo = transport => ({ transport, id: "unknown", status: "unknown", identitySource: "none", name: null, version: null, clientType: null, sessionId: null, reason: "test", capabilities: {} });
const page = snapshot => ({ querySelector: () => ({ textContent: JSON.stringify(snapshot) }) });
const framed = { parent: {}, location: { origin: "null" } };

test("a Codex MCP App page long-polls the backend through the adapter's own MCP connection", async () => {
  const calls = [];
  let created = 0;
  const connection = { callTool: async (name, args) => { calls.push([name, args]); return new Promise(() => {}); }, connect: async () => {}, dispose: async () => {}, inspect: async () => ({ transport: "mcp-app", connected: false, identity: null, capabilities: null }) };
  const { adapter, source } = createCanvasComposition({
    document: page({ hostInfo: hostInfo("mcp-app"), graphBackend: { url: "http://127.0.0.1:1", token: "a".repeat(64) }, serverInfo: { name: "graph-skill-canvas" } }),
    window: framed, connections: { "mcp-app": () => { created += 1; return connection; } },
  });
  assert.ok(adapter);
  source.connect({ receive: assert.fail, fail: assert.fail });
  source.selectRoot("C:/skill");
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(calls, [["watch_graph", { skill_root: "C:/skill", timeout_ms: 20000 }]]);
  assert.equal(created, 1);
  source.dispose();
});

test("an HTTP page and a standalone page keep the SSE backend connection", () => {
  const http = createCanvasComposition({ document: page({ hostInfo: hostInfo("http-bridge"), graphBackend: { url: "http://127.0.0.1:1", token: "a".repeat(64) } }), window: { parent: undefined, location: { origin: "http://127.0.0.1:1" } } });
  assert.ok(http.source && typeof http.source.selectRoot === "function");
  const standalone = createCanvasComposition({ document: { querySelector: () => null }, window: {} });
  assert.equal(standalone.adapter, null);
  assert.equal(standalone.source, null);
});
