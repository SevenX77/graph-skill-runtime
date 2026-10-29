import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { capability as claudeCapability, invoke as callClaude } from "../../../plugin_base/host_interfaces/tools/call/claude.mjs";

const mcpName = "mcp__graph-skill-canvas__inspect_graph";
const listed = [{ name: "Read", mcp: false }, { name: mcpName, mcp: true }];
const argumentsJson = { skill_root: "C:/business/示例" };
const invokeClaude = (api, tool, args = argumentsJson, tools = listed) =>
  callClaude(api, { tools, args: { tool, arguments: args }, guard: async () => {} });

test("tools.call accepts a named JSON tool but rejects nonportable or ambiguous references", () => {
  assert.deepEqual(validateArguments("tools.call", { tool: { name: "Read", scope: "session" }, arguments: { file_path: "C:/x" } }),
    { tool: { name: "Read", scope: "session" }, arguments: { file_path: "C:/x" } });
  for (const tool of [{ name: "" }, { name: "Read", scope: "global" }, { name: "Read", extra: true }]) {
    assert.throws(() => validateArguments("tools.call", { tool, arguments: {} }));
  }
  assert.throws(() => validateArguments("tools.call", { tool: { name: "Read" }, arguments: { x: () => {} } }));
});

test("Codex calls only the originating server and returns the direct SDK result", async () => {
  const calls = [];
  const app = { getHostCapabilities: () => ({ serverTools: {} }), getHostContext: () => ({}),
    callServerTool: async params => { calls.push(params); return { content: [{ type: "text", text: "direct" }] }; } };
  const driver = codexAdapter(app, { originatingServer: "graph-skill-canvas" });
  const result = await driver.invoke("tools.call", { tool: { name: "inspect_graph", server: "graph-skill-canvas", scope: "originating-server" }, arguments: argumentsJson });
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data.content, [{ type: "text", text: "direct" }]);
  assert.deepEqual(calls, [{ name: "inspect_graph", arguments: argumentsJson }]);
  for (const tool of [{ name: "Read", scope: "session" }, { name: "inspect_graph", server: "foreign" }]) {
    assert.equal((await driver.invoke("tools.call", { tool, arguments: {} })).status, "unsupported");
  }
  assert.equal(calls.length, 1);
});

test("Codex propagates tool execution error; unadvertised host cannot call", async () => {
  const app = { getHostCapabilities: () => ({ serverTools: {} }), getHostContext: () => ({}),
    callServerTool: async () => ({ isError: true, content: [{ type: "text", text: "invalid" }] }) };
  assert.equal((await codexAdapter(app, { originatingServer: "graph-skill-canvas" }).invoke("tools.call", { tool: { name: "inspect_graph" }, arguments: {} })).status, "error");
  app.getHostCapabilities = () => ({});
  assert.equal((await codexAdapter(app).invoke("tools.call", { tool: { name: "inspect_graph" }, arguments: {} })).status, "unsupported");
});

test("Claude explicit MCP tool and native tool go through listed, permission-checking tool.call, not mcp.call or prompt", async () => {
  const calls = [];
  const api = { tool: { call: async input => { calls.push(input); return { result: { ok: true } }; } },
    mcp: { call: () => assert.fail("mcp.call bypasses the Mod permission prompt") },
    prompt: { submit: () => assert.fail("direct tool call must not send a conversation message") } };
  const explicit = await invokeClaude(api, { server: "graph-skill-canvas", name: "inspect_graph", scope: "session" });
  assert.equal(explicit.status, "completed");
  assert.deepEqual(explicit.data, { result: { ok: true } });
  const native = await invokeClaude(api, { name: "Read", scope: "session" }, { file_path: "C:/x" });
  assert.equal(native.status, "completed");
  assert.deepEqual(calls, [{ skill_root: "C:/business/示例", tool: mcpName }, { file_path: "C:/x", tool: "Read" }]);
});

test("Claude refuses missing/unlisted or ambiguous targets without dispatch", async () => {
  const calls = [];
  const api = { tool: { call: async value => { calls.push(value); return { result: {} }; } } };
  for (const tool of [{ name: "absent" }, { server: "wrong", name: "inspect_graph" },
    { name: "inspect_graph", server: "graph-skill-canvas", scope: "originating-server" }]) {
    assert.equal((await invokeClaude(api, tool)).status, "unsupported");
  }
  for (const args of [{ tool: "Bash" }, { tool_use_id: "forged" }, { consent: "I approved" }, { agentId: "other" }]) {
    await assert.rejects(invokeClaude(api, { name: "Read" }, args), error => error.outcome === "not-sent");
  }
  assert.equal(calls.length, 0);
});

test("Claude denial and errored tool result do not claim completion", async () => {
  const responses = [{ deny: "not allowed" }, { isError: true, text: "execution failed", result: "failure" }];
  const api = { tool: { call: async () => responses.shift() } };
  await assert.rejects(invokeClaude(api, { name: "Read" }), error => error.outcome === "rejected" && /not allowed/.test(error.message) && error.data.deny === "not allowed");
  const errored = await invokeClaude(api, { name: "Read" });
  assert.equal(errored.status, "error");
  assert.equal(errored.data.isError, true);
  assert.equal(claudeCapability([]).state, "unavailable");
  assert.equal(claudeCapability(listed).state, "available");
});
