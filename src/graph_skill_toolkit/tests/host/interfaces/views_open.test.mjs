import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { mcpCapabilities } from "../../../plugin_base/adapters/codex/driver/registry.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { nativeCapabilities, executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { fakeBrowser } from "../../support/browser.mjs";

const web = { resource: { kind: "web", url: "https://example.com/docs" }, reuseKey: "docs", activate: true };
const file = { resource: { kind: "file", path: "C:/business/SKILL.md", line: 3 }, reuseKey: "skill", activate: false };

test("views.open accepts its two scoped resource shapes but rejects unsafe substitutions", () => {
  assert.deepEqual(validateArguments("views.open", web), web);
  assert.deepEqual(validateArguments("views.open", file), file);
  for (const input of [
    { ...web, resource: { kind: "web", url: "file:///C:/business/SKILL.md" } },
    { ...web, resource: { kind: "web", url: "https://u:p@example.com/" } },
    { ...web, resource: { kind: "web", url: "javascript:alert(1)" } },
    { ...file, resource: { kind: "file", path: "./SKILL.md" } },
    { ...file, resource: { kind: "file", path: "C:/business/SKILL.md", line: 0 } },
    { ...web, extra: "not in contract" },
  ]) assert.throws(() => validateArguments("views.open", input));
});

test("Codex advertised openLink, files and display do not supply a manageable view", async () => {
  const host = { experimental: { "openai/files": { open: {} } }, serverTools: {}, message: { text: {} } };
  const calls = [];
  const app = {
    getHostCapabilities: () => host,
    getHostContext: () => ({ availableDisplayModes: ["fullscreen"] }),
    openLink: async args => { calls.push(["openLink", args]); return { isError: false }; },
    requestDisplayMode: async args => { calls.push(["requestDisplayMode", args]); return { mode: "fullscreen" }; },
    callServerTool: async args => { calls.push(["callServerTool", args]); return {}; },
  };
  const cap = mcpCapabilities(host, app.getHostContext())["views.open"];
  assert.equal(cap.state, "unknown");
  assert.match(cap.detail, /openLink.*viewId/);
  const driver = codexAdapter(app);
  assert.equal((await driver.invoke("views.open", web)).status, "unsupported");
  assert.equal((await driver.invoke("views.open", file)).status, "unsupported");
  assert.deepEqual(calls, []);
});

const claudeBridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "page-a" };
const open = (id, args) => ({ id, action: "views.open", args, key: claudeBridge.key });

test("Claude opens an own Browser tab, reuses it by reuseKey and reports a hidden pane honestly", async () => {
  const browser = fakeBrowser({ tabs: [{ tabId: "user-tab", origin: "https://user.example", isActive: true }] });
  const state = createModState();
  assert.equal(nativeCapabilities(browser.api ? (await browser.api.tool.list()) : [])["views.open"].state, "available");
  const first = await executeBridgeAction(browser.api, state, claudeBridge, open("o1", web));
  assert.equal(first.status, "accepted");
  assert.match(first.evidence.limits[0], /面板保持隐藏/);
  assert.equal(first.evidence.observed.active, true);
  assert.equal(first.evidence.observed.paneDisplayed, false);
  browser.paneDisplayed = true;
  const again = await executeBridgeAction(browser.api, state, claudeBridge, open("o2", { ...web, resource: { kind: "web", url: "https://example.com/next" } }));
  assert.equal(again.status, "completed");
  assert.equal(again.data.viewId, first.data.viewId);
  assert.equal(browser.calls.filter(call => call.tool.endsWith("preview_start")).length, 1);
  assert.equal(browser.calls.filter(call => call.tool.endsWith("navigate")).length, 1);
  assert.equal(browser.tabs.find(tab => tab.tabId === "user-tab").isActive, false);
  const fileView = await executeBridgeAction(browser.api, state, claudeBridge, open("o3", file));
  assert.equal(fileView.status, "unsupported");
});


test("Claude view inventory errors keep raw replies and no-window replies are rejected", async () => {
  for (const [raw, outcome] of [[{ text: "unrecognized inventory" }, "not-sent"], [{ text: "This session isn't open in any window right now, so its view was left alone." }, "rejected"]]) {
    const browser = fakeBrowser(); browser.api.tool.call = async () => raw;
    await assert.rejects(executeBridgeAction(browser.api, createModState(), claudeBridge, open("bad", web)), error => {
      assert.equal(error.outcome, outcome); assert.deepEqual(error.data, raw); return true;
    });
  }
});
