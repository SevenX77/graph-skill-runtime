import assert from "node:assert/strict";
import test from "node:test";
import { capability as codexCapability } from "../../../plugin_base/host_interfaces/views/list/codex.mjs";
import { capability as claudeCapability } from "../../../plugin_base/host_interfaces/views/list/claude.mjs";
import { executeBridgeAction, nativeCapabilities } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { CONTEXT_TOOL } from "../../../plugin_base/adapters/claude/mod/host_tools/index.mjs";
import { fakeBrowser } from "../../support/browser.mjs";

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "C:/business/skill" };
const request = id => ({ id, action: "views.list", args: {}, key: bridge.key });
function peer(payload, toolInventory = [{ name: CONTEXT_TOOL }]) {
  const calls = [];
  return {
    calls,
    api: {
      session: { id: async () => "session-a" },
      tool: {
        list: async () => toolInventory,
        call: async input => { calls.push(input); return payload; },
      },
    },
  };
}
function rawTabs(tabs, note = "The Browser pane is currently hidden.") {
  return { content: [{ type: "text", text: JSON.stringify({ browserOpen: true, tabs }) + "\n" + note }] };
}

test("Claude returns unavailable without the current tool, and Codex inventory stays unknown", async () => {
  const { api, calls } = peer(rawTabs([]), []);
  assert.equal(nativeCapabilities([])["views.list"].state, "unavailable");
  const result = await executeBridgeAction(api, createModState(), bridge, request("missing"));
  assert.equal(result.status, "unsupported");
  assert.equal(result.data.capabilityState, "unavailable");
  assert.equal(calls.length, 0);
  assert.equal(codexCapability({ experimental: { "openai/files": {} }, serverTools: {} }).state, "unknown");
});

test("Claude rejects an invalid native tab identifier before building a view list", async () => {
  const { api } = peer(rawTabs([{ tabId: 42, origin: "http://site.test", isActive: true }]));
  await assert.rejects(
    executeBridgeAction(api, createModState(), bridge, request("bad-native-id")),
    error => error?.outcome === "not-sent",
  );
});

test("Claude lists only the views this page opened, never the user's tabs", async () => {
  const browser = fakeBrowser({ tabs: [{ tabId: "user-tab", origin: "https://user.example", isActive: true }] });
  const state = createModState();
  const empty = await executeBridgeAction(browser.api, state, bridge, request("l0"));
  assert.deepEqual([empty.status, empty.data.scope, empty.data.views], ["completed", "own-views", []]);
  const opened = await executeBridgeAction(browser.api, state, bridge, { id: "o1", action: "views.open", args: { resource: { kind: "web", url: "https://example.com/" }, reuseKey: "k", activate: false }, key: bridge.key });
  const listed = await executeBridgeAction(browser.api, state, bridge, request("l1"));
  assert.deepEqual(listed.data.views.map(view => view.viewId), [opened.data.viewId]);
  const other = { ...bridge, token: "b".repeat(64) };
  assert.deepEqual((await executeBridgeAction(browser.api, state, other, { ...request("l2"), key: other.key })).data.views, []);
  browser.tabs.splice(browser.tabs.findIndex(tab => tab.tabId !== "user-tab"), 1);
  assert.deepEqual((await executeBridgeAction(browser.api, state, bridge, request("l3"))).data.views, []);
});
