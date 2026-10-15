import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { executeBridgeAction, nativeCapabilities } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { capability as codexCapability } from "../../../plugin_base/host_interfaces/views/close/codex.mjs";

const root = "C:/business/hello-world";
const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: root };
const request = (id, viewId) => ({ id, action: "views.close", args: { viewId }, key: root });

test("views.close validates an opaque connection view ID and rejects extra host tab IDs", () => {
  assert.deepEqual(validateArguments("views.close", { viewId: "view-1" }), { viewId: "view-1" });
  for (const args of [{}, { viewId: "" }, { viewId: 7 }, { viewId: "view-1", tabId: "native-tab" }]) {
    assert.throws(() => validateArguments("views.close", args));
  }
});

test("Claude does not close existing or forged tabs even when native tabs_close is listed", async () => {
  const state = createModState();
  const tools = [
    { name: "mcp__Claude_Browser__tabs_context" },
    { name: "mcp__Claude_Browser__tabs_close" },
    { name: "mcp__Claude_Browser__tabs_select" },
  ];
  assert.equal(nativeCapabilities(tools)["views.close"].state, "unknown");
  const calls = [];
  const api = {
    session: { id: async () => "session-a" },
    tool: {
      list: async () => tools,
      call: async input => {
        calls.push(input);
        if (input.tool.endsWith("tabs_context")) {
          return { result: { tabs: [{ tabId: "existing", isActive: true, origin: "https://example.com" }] } };
        }
        assert.fail("The close tool must never run for an unowned tab");
      },
    },
  };
  const listed = await executeBridgeAction(api, state, bridge,
    { id: "list", action: "views.list", args: {}, key: root });
  assert.equal(listed.status, "completed");
  assert.equal(listed.data.views[0].owned, false);
  for (const viewId of [listed.data.views[0].viewId, "existing", "forged-view-id"]) {
    const before = calls.length;
    const result = await executeBridgeAction(api, state, bridge, request("close-" + before, viewId));
    assert.equal(result.status, "unsupported");
    assert.equal(result.data.capabilityState, "unknown");
    assert.equal(calls.length, before);
  }
  assert.equal(calls.filter(call => call.tool.endsWith("tabs_close")).length, 0);
});

test("Codex declines close even when unrelated MCP App capabilities are advertised", async () => {
  let effects = 0;
  const app = {
    getHostCapabilities: () => ({
      message: { text: {} }, serverTools: {}, updateModelContext: { structuredContent: {} },
      experimental: { "openai/files": {}, "openai/message": { draft: {} } },
    }),
    getHostContext: () => ({ availableDisplayModes: ["inline", "fullscreen"] }),
    openLink: async () => { effects++; },
    requestDisplayMode: async () => { effects++; },
    callServerTool: async () => { effects++; },
  };
  assert.equal(codexCapability().state, "unknown");
  const result = await codexAdapter(app).invoke("views.close", { viewId: "view-1" });
  assert.equal(result.status, "unsupported");
  assert.equal(effects, 0);
});
