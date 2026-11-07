import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { nativeCapabilities } from "../../../plugin_base/adapters/claude/mod/operations/registry.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";

function pair() {
  const view = {}, host = {};
  view.start = host.start = async () => {};
  view.send = async message => queueMicrotask(() => host.onmessage?.(message));
  host.send = async message => queueMicrotask(() => view.onmessage?.(message));
  view.close = async () => view.onclose?.();
  host.close = async () => host.onclose?.();
  return { view, host };
}

async function sdkHost(t, modes, actualMode) {
  const { view, host } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "test" }, {});
  const requests = [];
  if (actualMode !== "sdk-default") bridge.onrequestdisplaymode = async ({ mode }) => {
    requests.push(mode);
    return { mode: actualMode ?? mode };
  };
  const app = new App({ name: "Graph Skill canvas", version: "test" }, {}, { autoResize: false });
  t.after(async () => { await app.close(); await bridge.close(); });
  await bridge.connect(host);
  await app.connect(view);
  if (modes) {
    bridge.setHostContext({ availableDisplayModes: modes, displayMode: "inline" });
    await new Promise(resolve => setImmediate(resolve));
  }
  return { app, requests, adapter: codexAdapter(app) };
}

test("Codex SDK display-mode request sends only a declared mode and reports the actual response", async t => {
  const { app, requests, adapter } = await sdkHost(t, ["inline", "fullscreen"], "fullscreen");
  const cap = (await import("../../../plugin_base/adapters/codex/driver/registry.mjs")).mcpCapabilities(app.getHostCapabilities(), app.getHostContext())["views.requestDisplayMode"];
  assert.equal(cap.state, "available");
  assert.deepEqual(cap.constraints.modes, ["inline", "fullscreen"]);
  const result = await adapter.invoke("views.requestDisplayMode", { mode: "fullscreen" });
  assert.equal(result.status, "completed");
  assert.deepEqual(result.data, { mode: "fullscreen" });
  assert.deepEqual(requests, ["fullscreen"]);
  assert.equal((await adapter.invoke("views.requestDisplayMode", { mode: "pip" })).status, "unsupported");
  assert.deepEqual(requests, ["fullscreen"]);
});

test("A returned different mode does not claim the requested mode was set", async t => {
  const { adapter, requests } = await sdkHost(t, ["inline", "fullscreen"], "inline");
  const result = await adapter.invoke("views.requestDisplayMode", { mode: "fullscreen" });
  assert.equal(result.status, "rejected");
  assert.deepEqual(result.data, { mode: "inline" });
  assert.deepEqual(requests, ["fullscreen"]);
});

test("SDK default bridge can return unchanged current mode despite advertised support", async t => {
  const { adapter } = await sdkHost(t, ["inline", "fullscreen"], "sdk-default");
  const result = await adapter.invoke("views.requestDisplayMode", { mode: "fullscreen" });
  assert.equal(result.status, "rejected");
  assert.deepEqual(result.data, { mode: "inline" });
});

test("An explicit empty modes declaration is unavailable without a host request", async t => {
  const { app, adapter, requests } = await sdkHost(t, [], "inline");
  const cap = (await import("../../../plugin_base/adapters/codex/driver/registry.mjs")).mcpCapabilities(app.getHostCapabilities(), app.getHostContext())["views.requestDisplayMode"];
  assert.equal(cap.state, "unavailable");
  assert.equal((await adapter.invoke("views.requestDisplayMode", { mode: "fullscreen" })).status, "unsupported");
  assert.deepEqual(requests, []);
});

test("No host context declaration remains unknown and does not dispatch", async t => {
  const { adapter, requests } = await sdkHost(t, null, "fullscreen");
  assert.equal((await adapter.invoke("views.requestDisplayMode", { mode: "fullscreen" })).status, "unsupported");
  assert.deepEqual(requests, []);
});

test("Claude tool inventory does not turn a preview or browser tab into a canvas mode API", () => {
  const result = nativeCapabilities([
    { name: "tabs_context" }, { name: "tabs_select" }, { name: "mcp__ccd_view__show_pane" },
    { name: "preview_start" }, { name: "Skill" },
  ]);
  assert.equal(result["views.requestDisplayMode"].state, "unavailable");
});

// Claude Code 2.1.309 layout tools, as the host answers them: the pane tool and the sidebar tool reply with a
// sentence, the two layout readers with a sentence or a JSON object.
const CLAUDE_TOOLS = ["mcp__ccd_view__show_pane", "mcp__ccd_window__set_sidebar_collapsed", "mcp__ccd_window__get_window_layout", "mcp__ccd_view__get_layout"]
  .map(name => ({ name, mcp: true }));
function claudeHost(layout) {
  const calls = [];
  const api = { session: { id: async () => "s" }, tool: { list: async () => CLAUDE_TOOLS, call: async input => {
    calls.push(input);
    const { tool, ...args } = input;
    if (tool === "mcp__ccd_view__show_pane") return layout.onScreen === false
      ? { result: [{ type: "text", text: "This session isn't open in any window right now, so its view was left alone." }] }
      : (layout.panes.includes("preview") || layout.panes.push("preview"), { result: [{ type: "text", text: "Showing the preview pane." }] });
    if (tool === "mcp__ccd_window__set_sidebar_collapsed") {
      if (layout.refuseSidebar) return { result: [{ type: "text", text: "The window is too narrow to show the sidebar." }] };
      layout.sidebarCollapsed = args.collapsed; return { result: [{ type: "text", text: args.collapsed ? "Collapsed the sidebar." : "Expanded the sidebar." }] };
    }
    if (tool === "mcp__ccd_window__get_window_layout") return { result: [{ type: "text", text: JSON.stringify({ main_window: { tab: "code", sidebar_collapsed: layout.sidebarCollapsed, panes: [] }, this_session: { on_screen: layout.onScreen !== false, shown_in: "the main pane" } }) }] };
    if (tool === "mcp__ccd_view__get_layout") return { result: [{ type: "text", text: JSON.stringify({ views: [{ placement: "primary" }], open_panes: layout.panes, transcript_view: "normal" }) }] };
    throw new Error("unexpected tool " + tool);
  } } };
  return { api, calls };
}
const claudeBridge = { url: "http://127.0.0.1:12345", token: "t", key: "p" };
const claudeRequest = (id, mode) => ({ id, action: "views.requestDisplayMode", args: { mode }, key: "p" });

test("Claude sets the container's display mode through the host's pane and sidebar tools and reads the mode back", async () => {
  const layout = { sidebarCollapsed: false, panes: [] };
  const { api, calls } = claudeHost(layout);
  const cap = nativeCapabilities(CLAUDE_TOOLS)["views.requestDisplayMode"];
  assert.equal(cap.state, "available");
  assert.deepEqual(cap.constraints.modes, ["inline", "fullscreen"]);
  const full = await executeBridgeAction(api, createModState(), claudeBridge, claudeRequest("full", "fullscreen"));
  assert.equal(full.status, "completed");
  assert.deepEqual(full.data, { mode: "fullscreen", layout: { onScreen: true, sidebarCollapsed: true, paneOpen: true } });
  assert.deepEqual(calls.map(item => item.tool), ["mcp__ccd_view__show_pane", "mcp__ccd_window__set_sidebar_collapsed", "mcp__ccd_window__get_window_layout", "mcp__ccd_view__get_layout"]);
  assert.deepEqual(calls[1], { tool: "mcp__ccd_window__set_sidebar_collapsed", collapsed: true });
  const inline = await executeBridgeAction(api, createModState(), claudeBridge, claudeRequest("inline", "inline"));
  assert.equal(inline.status, "completed");
  assert.equal(inline.data.mode, "inline");
  assert.equal(layout.sidebarCollapsed, false);
});

test("Claude reports a mode the host did not set as rejected, and pip as unsupported without a call", async () => {
  const refused = claudeHost({ sidebarCollapsed: false, panes: [], refuseSidebar: true });
  const result = await executeBridgeAction(refused.api, createModState(), claudeBridge, claudeRequest("narrow", "fullscreen"));
  assert.equal(result.status, "rejected");
  assert.deepEqual(result.data, { mode: "inline", layout: { onScreen: true, sidebarCollapsed: false, paneOpen: true } });
  const offScreen = claudeHost({ sidebarCollapsed: false, panes: [], onScreen: false });
  const away = await executeBridgeAction(offScreen.api, createModState(), claudeBridge, claudeRequest("away", "fullscreen"));
  assert.equal(away.status, "rejected");
  assert.match(away.message, /isn't open in any window/);
  assert.equal(offScreen.calls.length, 1, "the sidebar is left alone when the session is off screen");
  const pip = claudeHost({ sidebarCollapsed: false, panes: [] });
  assert.equal((await executeBridgeAction(pip.api, createModState(), claudeBridge, claudeRequest("pip", "pip"))).status, "unsupported");
  assert.deepEqual(pip.calls, []);
});
