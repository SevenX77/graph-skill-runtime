import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments } from "../../../plugin_base/ports/host/contract.mjs";
import { mcpCapabilities } from "../../../plugin_base/adapters/codex/driver/registry.mjs";
import { codexAdapter } from "../../../plugin_base/adapters/codex/driver/index.mjs";
import { nativeCapabilities, executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";

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

test("Claude Browser preview and tab tools do not imply reusable owned view semantics", async () => {
  const listed = [
    { name: "mcp__Claude_Browser__preview_start" },
    { name: "mcp__Claude_Browser__tabs_create" },
    { name: "mcp__Claude_Browser__tabs_context" },
    { name: "mcp__Claude_Browser__tabs_select" },
    { name: "mcp__Claude_Browser__tabs_close" },
    { name: "mcp__ccd_view__show_pane" },
  ];
  const calls = [], state = createModState();
  const api = { session: { id: async () => "session-a" }, tool: {
    list: async () => listed,
    call: async input => { calls.push(input); return { result: { tabId: "pre-existing" } }; },
  } };
  const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), skillRoot: "C:/business" };
  const cap = nativeCapabilities(listed)["views.open"];
  assert.equal(cap.state, "unknown");
  assert.match(cap.detail, /reuseKey.*activate=false/);
  for (const [id, args] of [["web", web], ["file", file]]) {
    const result = await executeBridgeAction(api, state, bridge, { id, action: "views.open", args, skillRoot: bridge.skillRoot });
    assert.equal(result.status, "unsupported");
    assert.equal(result.data.capabilityState, "unknown");
  }
  assert.deepEqual(calls, []);
  assert.equal(state.views.size, 0);
});
