import assert from "node:assert/strict";
import test from "node:test";
import { createHostBridge } from "../../../plugin_base/adapters/claude/bridge/server.mjs";
import { identifyHost, hostIdentityKey } from "../../../plugin_base/adapters/detection/index.mjs";
import { nativeCapabilities } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { readPermissionMode } from "../../../plugin_base/adapters/claude/mod/operations/tools/index.mjs";
import { createModState, pollBridges } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { permissionModeLabel } from "../../../apps/interface_lab/application/result_status/index.mjs";

const SESSION_TOOL = "mcp__ccd_session_mgmt__get_session";
const tools = [{ name: SESSION_TOOL }, { name: "mcp__Claude_Browser__preview_start" }, { name: "mcp__Claude_Browser__navigate" }, { name: "mcp__Claude_Browser__tabs_context" }, { name: "mcp__Claude_Browser__tabs_select" }, { name: "mcp__Claude_Browser__tabs_close" }];
const identity = { name: "Claude Code", version: "2.1.309", client_type: "claude_code", sessionId: "session-a", source: "claude-mod-session" };
const receipt = mode => ({ result: [{ type: "text", text: JSON.stringify({ sessionId: "local_a", fastMode: { state: "off" }, permissionMode: mode }) }] });

test("the mode is read from the host's session tool only when the engine already allows the call", async () => {
  const calls = [];
  const $ = decision => ({ tool: { check: async input => { calls.push(input); return { decision }; }, call: async input => { calls.push(input); return receipt("auto"); } } });
  assert.equal(await readPermissionMode($("allow"), tools), "auto");
  assert.deepEqual(calls, [{ tool: SESSION_TOOL, input: { session_id: "self" } }, { session_id: "self", tool: SESSION_TOOL }]);
  calls.length = 0;
  assert.equal(await readPermissionMode($("ask"), tools), null);
  assert.equal(calls.length, 1, "a call that needs asking does not run");
  assert.equal(await readPermissionMode($("allow"), []), null, "a host without the tool has no readable mode");
  assert.equal(await readPermissionMode({ tool: { check: async () => { throw new Error("refused"); } } }, tools), null);
  assert.equal(await readPermissionMode({ tool: { check: async () => ({ decision: "allow" }), call: async () => ({ deny: "no" }) } }, tools), null);
});

test("only the current mode's limits mark capabilities, and the operation stays available", () => {
  const auto = nativeCapabilities(tools, { permissionMode: "auto" });
  assert.deepEqual(Object.entries(auto).filter(([, item]) => item.modeLimit).map(([id, item]) => [id, item.modeLimit.effect]).sort(),
    [["tools.call", "partial"], ["views.close", "blocked"], ["views.open", "blocked"]]);
  assert.equal(auto["views.open"].state, "available");
  assert.equal(auto["views.open"].modeLimit.mode, "auto");
  for (const permissionMode of ["default", "bypassPermissions", "constructor", null, undefined]) {
    assert.equal(Object.values(nativeCapabilities(tools, { permissionMode })).some(item => item.modeLimit), false);
  }
});

test("a limit on an operation the host does not offer adds nothing", () => {
  assert.equal(nativeCapabilities([], { permissionMode: "auto" })["views.open"].modeLimit, undefined);
});

test("HostInfo carries the mode and its limits; a changed mode is not a changed identity", () => {
  const capabilities = nativeCapabilities(tools, { permissionMode: "auto" });
  const info = identifyHost({ transport: "http-bridge", connected: true, identity: { ...identity, permission_mode: "auto" }, capabilities });
  assert.equal(info.id, "claude");
  assert.equal(info.permissionMode, "auto");
  assert.equal(info.capabilities["views.open"].modeLimit.effect, "blocked");
  const before = identifyHost({ transport: "http-bridge", connected: true, identity, capabilities: {} });
  assert.equal(before.permissionMode, null);
  assert.equal(hostIdentityKey(before), hostIdentityKey(info));
  assert.equal(identifyHost({ transport: "http-bridge", connected: true, identity, capabilities: { "views.open": { state: "available", detail: "x", modeLimit: { mode: "auto", effect: "maybe", detail: "x" } } } }).id, "unknown");
});

test("the poll reports the mode to the page, every five polls, and a slow read does not hold it up", async t => {
  const owner = createHostBridge({ responseWaitMs: 5 }); t.after(() => owner.close());
  const view = await owner.createView("C:/business/mode");
  let mode = "auto", reads = 0, release = () => {};
  let gate = Promise.resolve();
  const $ = {
    session: { id: async () => "session-a", version: async () => ({ version: "2.1.309" }), usage: async () => ({}) },
    tool: { list: async () => tools, check: async () => ({ decision: "allow" }), call: async () => { reads++; await gate; return receipt(mode); } },
    http: { fetch: async (url, init) => { const response = await fetch(url, init); return { ok: response.ok, status: response.status, text: await response.text() }; } },
    ui: { log() {} },
  };
  const state = createModState();
  state.bridges.set(view.mod.url + "/" + view.mod.token, view.mod);
  const live = async () => {
    const response = await fetch(view.browser.url + "/capabilities", { headers: { Authorization: "Bearer " + view.browser.token } });
    return identifyHost({ transport: "http-bridge", ...await response.json() });
  };
  const settle = () => new Promise(resolve => setImmediate(resolve));
  await pollBridges($, state); await settle();
  await pollBridges($, state);
  assert.equal((await live()).permissionMode, "auto");
  assert.equal((await live()).capabilities["views.open"].modeLimit.effect, "blocked");
  assert.equal(reads, 1);
  mode = "default";
  for (let poll = 0; poll < 3; poll++) await pollBridges($, state);
  assert.equal(reads, 1, "the mode is not read on every poll");
  await pollBridges($, state); await settle();
  assert.equal(reads, 2);
  await pollBridges($, state);
  assert.equal((await live()).permissionMode, "default");
  assert.equal((await live()).capabilities["views.open"].modeLimit, undefined);
  gate = new Promise(resolve => { release = resolve; });
  for (let poll = 0; poll < 5; poll++) await pollBridges($, state);
  assert.equal(reads, 3, "the poll finishes while a read is still waiting");
  release();
});

test("the lab names each mode and shows an unread mode as unknown", () => {
  assert.equal(permissionModeLabel("auto"), "自动");
  assert.equal(permissionModeLabel("default"), "手动");
  assert.equal(permissionModeLabel("bypassPermissions"), "跳过权限确认");
  assert.equal(permissionModeLabel(null), "未知");
  assert.equal(permissionModeLabel("newMode"), "newMode");
  assert.equal(permissionModeLabel("constructor"), "constructor");
});
