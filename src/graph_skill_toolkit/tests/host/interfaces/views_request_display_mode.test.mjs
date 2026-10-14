import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { codexAdapter } from "../../../adapters/codex/driver/index.mjs";
import { nativeCapabilities } from "../../../adapters/claude/mod/operations/registry.mjs";

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
  const cap = (await import("../../../adapters/codex/driver/registry.mjs")).mcpCapabilities(app.getHostCapabilities(), app.getHostContext())["views.requestDisplayMode"];
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
  const cap = (await import("../../../adapters/codex/driver/registry.mjs")).mcpCapabilities(app.getHostCapabilities(), app.getHostContext())["views.requestDisplayMode"];
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
  assert.equal(result["views.requestDisplayMode"].state, "unknown");
});
