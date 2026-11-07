import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { mcpCapabilities } from "../../../plugin_base/adapters/codex/driver/registry.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { nativeCapabilities, executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";

const action = "files.revealDirectory";
const args = { path: "C:/projects/business-skill" };

test("directory reveal has its own absolute-path request, not a Graph Skill binding", () => {
  assert.deepEqual(validateArguments(action, args), args);
  assert.deepEqual(validateArguments(action, { path: "/home/user/business-skill" }), { path: "/home/user/business-skill" });
  assert.throws(() => validateArguments(action, { path: "business-skill" }), /绝对路径/);
  assert.throws(() => validateArguments(action, { ...args, key: args.path }), /未知的宿主接口参数/);
});

test("Codex file-open advertisement does not declare host file-browser directory reveal", async () => {
  // MCP Apps' experimental capability is extensible; this fixture advertises only the known file-open extension.
  const host = { experimental: { "openai/files": {} }, message: { text: {} } };
  const calls = [];
  const app = {
    getHostCapabilities: () => host,
    getHostContext: () => ({}),
    request: async (...values) => { calls.push(["request", ...values]); throw new Error("must not open a file as a directory"); },
    sendMessage: async (...values) => { calls.push(["message", ...values]); throw new Error("must not delegate to Agent"); },
  };
  assert.equal(mcpCapabilities(host)[action].state, "unknown");
  const result = await codexAdapter(app).invoke(action, args);
  assert.equal(result.status, "unsupported");
  assert.deepEqual(calls, []);
});

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "C:/projects/business-skill" };
const request = id => ({ id, action, args, key: bridge.key });
function claudeApi(tools, call) {
  const calls = [];
  const api = {
    session: { id: async () => "session-a" },
    tool: { list: async () => tools, call: async input => { calls.push(input); return call(input); } },
    prompt: { submit: async (...values) => { calls.push(["message", ...values]); throw new Error("must not delegate to Agent"); } },
  };
  return { api, calls };
}

test("Claude without the host reveal tool declares the route unavailable and substitutes nothing", async () => {
  // The captured host declaration in evidence/shared-html-pane-tool-schemas.json says pane=file opens a file.
  const tools = [{ name: "mcp__ccd_view__show_pane" }];
  const { api, calls } = claudeApi(tools, () => { throw new Error("must not substitute file pane"); });
  assert.equal(nativeCapabilities(tools)[action].state, "unavailable");
  const result = await executeBridgeAction(api, createModState(), bridge, request("reveal-none"), { sessionId: "session-a" });
  assert.equal(result.status, "unsupported");
  assert.equal(result.data.capabilityState, "unavailable");
  assert.deepEqual(calls, []);
});

test("Claude reveals a directory through the host's own reveal tool and reports acceptance with the host's sentence", async () => {
  // Claude Code 2.1.309 answers mcp__ccd_host__reveal_path with one text block naming the revealed folder.
  const tools = [{ name: "mcp__ccd_view__show_pane" }, { name: "mcp__ccd_host__reveal_path", mcp: true }];
  const reply = "Revealed folder C:\\projects\\business-skill in File Explorer.";
  const { api, calls } = claudeApi(tools, () => ({ result: [{ type: "text", text: reply }] }));
  const cap = nativeCapabilities(tools)[action];
  assert.equal(cap.state, "available");
  assert.equal(cap.scope, "session-folders");
  const result = await executeBridgeAction(api, createModState(), bridge, request("reveal-ok"), { sessionId: "session-a" });
  assert.equal(result.status, "accepted");
  assert.match(result.message, /Revealed folder/);
  assert.equal(result.data.reply, reply);
  assert.deepEqual(calls, [{ tool: "mcp__ccd_host__reveal_path", path: args.path }]);
});

test("Claude passes a host error or denial through instead of claiming the directory was revealed", async () => {
  const tools = [{ name: "mcp__ccd_host__reveal_path", mcp: true }];
  const outside = "`path` could not be resolved inside this session's working directory or granted folders.";
  const errored = claudeApi(tools, () => ({ isError: true, result: [{ type: "text", text: outside }] }));
  const result = await executeBridgeAction(errored.api, createModState(), bridge, request("reveal-outside"), { sessionId: "session-a" });
  assert.equal(result.status, "error");
  assert.equal(result.message, outside);
  const denied = claudeApi(tools, () => ({ deny: "Not allowed" }));
  await assert.rejects(executeBridgeAction(denied.api, createModState(), bridge, request("reveal-denied"), { sessionId: "session-a" }), error => error.outcome === "rejected");
  assert.equal(denied.calls.length, 1);
});
