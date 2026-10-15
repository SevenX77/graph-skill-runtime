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

test("Claude Files-pane file tool does not establish native directory navigation", async () => {
  // The captured host declaration in evidence/shared-html-pane-tool-schemas.json says pane=file opens a file.
  const tools = [{ name: "mcp__ccd_view__show_pane" }];
  const calls = [];
  const api = {
    session: { id: async () => "session-a" },
    tool: {
      list: async () => tools,
      call: async (...values) => { calls.push(["tool", ...values]); throw new Error("must not substitute file pane"); },
    },
    prompt: {
      submit: async (...values) => { calls.push(["message", ...values]); throw new Error("must not delegate to Agent"); },
    },
  };
  const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "C:/projects/business-skill" };
  const request = { id: "reveal-test", action, args, key: bridge.key };
  assert.equal(nativeCapabilities(tools)[action].state, "unknown");
  const result = await executeBridgeAction(api, createModState(), bridge, request, { sessionId: "session-a" });
  assert.equal(result.status, "unsupported");
  assert.equal(result.data.capabilityState, "unknown");
  assert.deepEqual(calls, []);
});
