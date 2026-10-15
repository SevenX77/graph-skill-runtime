import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { executeBridgeAction, nativeCapabilities } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { capability as codexCapability } from "../../../plugin_base/host_interfaces/views/close/codex.mjs";
import { fakeBrowser } from "../../support/browser.mjs";

const root = "C:/business/hello-world";
const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: root };
const request = (id, viewId) => ({ id, action: "views.close", args: { viewId }, key: root });

test("views.close validates an opaque connection view ID and rejects extra host tab IDs", () => {
  assert.deepEqual(validateArguments("views.close", { viewId: "view-1" }), { viewId: "view-1" });
  for (const args of [{}, { viewId: "" }, { viewId: 7 }, { viewId: "view-1", tabId: "native-tab" }]) {
    assert.throws(() => validateArguments("views.close", args));
  }
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

test("Claude closes only a view this page opened and rejects user or forged IDs", async () => {
  const browser = fakeBrowser({ tabs: [{ tabId: "user-tab", origin: "https://user.example", isActive: true }] });
  const state = createModState();
  assert.equal((await executeBridgeAction(browser.api, state, bridge, request("c0", "user-tab"))).status, "rejected");
  const opened = await executeBridgeAction(browser.api, state, bridge, { id: "o1", action: "views.open", args: { resource: { kind: "web", url: "https://example.com/" }, reuseKey: "k", activate: false }, key: root });
  const other = { ...bridge, token: "b".repeat(64) };
  assert.equal((await executeBridgeAction(browser.api, state, other, { ...request("c1", opened.data.viewId) })).status, "rejected");
  const closed = await executeBridgeAction(browser.api, state, bridge, request("c2", opened.data.viewId));
  assert.equal(closed.status, "completed");
  assert.deepEqual(browser.tabs.map(tab => tab.tabId), ["user-tab"]);
});
