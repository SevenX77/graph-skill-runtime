import assert from "node:assert/strict";
import test from "node:test";
import { capability as codexCapability } from "../../../host_interfaces/views/list/codex.mjs";
import { capability as claudeCapability } from "../../../host_interfaces/views/list/claude.mjs";
import { executeBridgeAction, nativeCapabilities } from "../../../adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../adapters/claude/mod/lifecycle/index.mjs";
import { CONTEXT_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), skillRoot: "C:/business/skill" };
const request = id => ({ id, action: "views.list", args: {}, skillRoot: bridge.skillRoot });
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

test("Claude lists real browser-tool text with hidden-pane tabs and stable connection handles", async () => {
  const tabs = [
    { tabId: "seed", origin: "http://127.0.0.1:8080", isActive: false },
    { tabId: "tab-1", origin: "file:///C:/business/skill/SKILL.md", isActive: true },
  ];
  const { api, calls } = peer(rawTabs(tabs));
  const state = createModState();
  assert.equal(claudeCapability([{ name: CONTEXT_TOOL }]).scope, "browser-tabs");
  const first = await executeBridgeAction(api, state, bridge, request("one"));
  const second = await executeBridgeAction(api, state, bridge, request("two"));
  assert.equal(first.status, "completed");
  assert.equal(first.data.scope, "browser-tabs");
  assert.deepEqual(first.data.views.map(view => ({ active: view.active, origin: view.origin, owned: view.owned })), [
    { active: false, origin: tabs[0].origin, owned: false },
    { active: true, origin: tabs[1].origin, owned: false },
  ]);
  assert.deepEqual(second.data.views.map(view => view.viewId), first.data.views.map(view => view.viewId));
  assert.ok(first.data.views.every(view => !tabs.some(tab => tab.tabId === view.viewId)));
  assert.deepEqual(calls, [{ tool: CONTEXT_TOOL }, { tool: CONTEXT_TOOL }]);
});

test("Claude returns unavailable without the current tool, and Codex inventory stays unknown", async () => {
  const { api, calls } = peer(rawTabs([]), []);
  assert.equal(nativeCapabilities([])["views.list"].state, "unavailable");
  const result = await executeBridgeAction(api, createModState(), bridge, request("missing"));
  assert.equal(result.status, "unsupported");
  assert.equal(result.data.capabilityState, "unavailable");
  assert.equal(calls.length, 0);
  assert.equal(codexCapability({ experimental: { "openai/files": {} }, serverTools: {} }).state, "unknown");
});

test("Claude refuses duplicate browser tab handles instead of reporting completion", async () => {
  const tabs = [{ tabId: "same", origin: "http://site.test", isActive: true }, { tabId: "same", origin: "http://site.test", isActive: true }];
  const { api } = peer(rawTabs(tabs));
  await assert.rejects(executeBridgeAction(api, createModState(), bridge, request("duplicate")),
    error => error?.outcome === "not-sent");
});

test("Claude rejects an invalid native tab identifier before building a view list", async () => {
  const { api } = peer(rawTabs([{ tabId: 42, origin: "http://site.test", isActive: true }]));
  await assert.rejects(
    executeBridgeAction(api, createModState(), bridge, request("bad-native-id")),
    error => error?.outcome === "not-sent",
  );
});

test("Claude does not transplant view handles to a second page connection", async () => {
  const { api } = peer(rawTabs([{ tabId: "seed", origin: "http://site.test", isActive: true }]));
  const state = createModState();
  const first = await executeBridgeAction(api, state, bridge, request("first"));
  const other = { ...bridge, token: "b".repeat(64) };
  const second = await executeBridgeAction(api, state, other, request("second"));
  assert.notEqual(first.data.views[0].viewId, second.data.views[0].viewId);
});
