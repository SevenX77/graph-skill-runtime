import assert from "node:assert/strict";
import test from "node:test";
import * as codex from "../../../host_interfaces/tools/list/codex.mjs";
import * as claude from "../../../host_interfaces/tools/list/claude.mjs";

const sourceTools = [
  { name: "inspect_graph", description: "Inspect", reference: { name: "inspect_graph", scope: "originating-server" } },
  { name: "list_canvas_tools", description: "List", reference: { name: "list_canvas_tools", scope: "originating-server" } },
];

test("Codex lists only the originating canvas server's page-callable tools", async () => {
  const calls = [];
  const app = { callServerTool: async request => {
    calls.push(request);
    return { structuredContent: { scope: "originating-server", complete: true, tools: sourceTools } };
  } };
  const result = await codex.invoke(app, { scope: "originating-server" });
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data.tools.map(tool => tool.reference), sourceTools.map(tool => tool.reference));
  assert.deepEqual(calls, [{ name: "list_canvas_tools", arguments: {} }]);
  assert.equal((await codex.invoke(app, { scope: "session" })).status, "unsupported");
  assert.equal(calls.length, 1);
});

test("Codex capability needs advertised serverTools; Claude exposes session scope", () => {
  assert.equal(codex.capability({}).state, "unavailable");
  assert.deepEqual({ state: codex.capability({ serverTools: {} }).state, scope: codex.capability({ serverTools: {} }).scope },
    { state: "available", scope: "originating-server" });
  assert.deepEqual({ state: claude.capability().state, scope: claude.capability().scope },
    { state: "available", scope: "session" });
});

test("Codex refuses forged, malformed, or errored server inventory", async () => {
  for (const data of [
    { scope: "session", complete: true, tools: sourceTools },
    { scope: "originating-server", complete: true, tools: [{ name: "inspect_graph", reference: { name: "foreign", scope: "originating-server" } }] },
    { scope: "originating-server", complete: true, tools: [null] },
  ]) {
    const result = await codex.invoke({ callServerTool: async () => ({ structuredContent: data }) }, {});
    assert.equal(result.status, "error");
  }
  const errored = await codex.invoke({ callServerTool: async () => ({ isError: true, content: [{ type: "text", text: "denied" }] }) }, {});
  assert.equal(errored.status, "error");
  const incomplete = await codex.invoke({ callServerTool: async () => ({ structuredContent: { scope: "originating-server", tools: [{ name: "inspect_graph" }] } }) }, {});
  assert.equal(incomplete.status, "completed");
  assert.equal(incomplete.data.complete, false);
});

test("Claude projects the actual current-session ToolInfo shape without inventing schemas", async () => {
  const tools = [
    { name: "Read", description: "Read files", mcp: false },
    { name: "mcp__graph-skill-canvas__inspect_graph", description: "Inspect graph", mcp: true },
  ];
  const result = await claude.invoke(undefined, { tools, args: {} });
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data.tools, [
    { name: "Read", description: "Read files", kind: "native", reference: { name: "Read", scope: "session" } },
    { name: "mcp__graph-skill-canvas__inspect_graph", description: "Inspect graph", kind: "mcp", reference: { name: "mcp__graph-skill-canvas__inspect_graph", scope: "session" } },
  ]);
  assert.equal((await claude.invoke(undefined, { tools, args: { scope: "originating-server" } })).status, "unsupported");
});

test("Claude marks missing legacy metadata unknown rather than inventing MCP membership", async () => {
  const result = await claude.invoke(undefined, { tools: [{ name: "mcp__unknown__tool" }], args: {} });
  assert.deepEqual(result.data.tools[0], { name: "mcp__unknown__tool", description: null, kind: "unknown",
    reference: { name: "mcp__unknown__tool", scope: "session" } });
});

test("Claude does not claim a completed inventory for malformed native ToolInfo", async () => {
  for (const tools of [[{ name: "" }], [{ name: "Read", description: "read", mcp: "yes" }], [null]]) {
    assert.equal((await claude.invoke(undefined, { tools, args: {} })).status, "error");
  }
});

test("Claude rejects an inventory larger than the Mod bridge receipt instead of completing without data", async () => {
  const result = await claude.invoke(undefined, { tools: [{ name: "Read", description: "x".repeat(60000), mcp: false }], args: {} });
  assert.equal(result.status, "error");
  assert.equal(result.data, undefined);
});
