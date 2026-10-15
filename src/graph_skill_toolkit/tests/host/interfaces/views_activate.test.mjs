import assert from "node:assert/strict";
import test from "node:test";
import { capability as claudeCapability } from "../../../plugin_base/host_interfaces/views/activate/claude.mjs";
import { capability as codexCapability } from "../../../plugin_base/host_interfaces/views/activate/codex.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";

const root = "C:/business/skill";
const bridge = { url: "http://127.0.0.1:10345", token: "a".repeat(64), key: root };
const tools = [{ name: "mcp__Claude_Browser__tabs_context" }, { name: "mcp__Claude_Browser__tabs_select" }];
const request = (id, action, args = {}) => ({ id, action, args, key: root });
const context = tabs => ({ result: { content: [{ type: "text", text: JSON.stringify({ browserOpen: true, tabs }) + "\nThe Browser pane is currently hidden." }] } });

function host({ after = null, onSelect = null } = {}) {
  const calls = [], tabs = [{ tabId: "seed", origin: "http://127.0.0.1:10345", isActive: false }, { tabId: "tab-1", origin: "file:///C:/SKILL.md", isActive: true }];
  let selected = false;
  const $ = {
    session: { id: async () => "session-a" },
    tool: { list: async () => tools, call: async input => {
      calls.push(input);
      if (input.tool === "mcp__Claude_Browser__tabs_context") {
        if (selected && after) return after();
        return context(tabs);
      }
      if (input.tool === "mcp__Claude_Browser__tabs_select") {
        selected = true;
        if (onSelect) return onSelect();
        for (const tab of tabs) tab.isActive = tab.tabId === input.tabId;
        return { result: { content: [{ type: "text", text: "Fronted tab " + input.tabId + "." }] } };
      }
      assert.fail("Unexpected host tool");
    } },
  };
  return { $, calls, tabs };
}

async function observedId($, state, owner = bridge) {
  const result = await executeBridgeAction($, state, owner, request("list-1", "views.list"));
  assert.equal(result.status, "completed");
  return result.data.views[0].viewId;
}

test("native inventory gates Claude selection and Codex display mode is not activation", () => {
  assert.equal(claudeCapability(tools).state, "available");
  assert.equal(claudeCapability(tools.slice(0, 1)).state, "unavailable");
  assert.equal(codexCapability().state, "unknown");
});

test("observed Claude Browser tab uses the native tabId, verifies active, and does not reveal a hidden pane", async () => {
  const { $, calls, tabs } = host(), state = createModState();
  const id = await observedId($, state);
  const result = await executeBridgeAction($, state, bridge, request("activate-1", "views.activate", { viewId: id }));
  assert.deepEqual({ status: result.status, data: result.data }, { status: "completed", data: { viewId: id, active: true } });
  assert.deepEqual(calls.map(item => item.tool), ["mcp__Claude_Browser__tabs_context", "mcp__Claude_Browser__tabs_context", "mcp__Claude_Browser__tabs_select", "mcp__Claude_Browser__tabs_context"]);
  assert.deepEqual(calls[2], { tool: "mcp__Claude_Browser__tabs_select", tabId: "seed" });
  assert.equal(tabs[0].isActive, true);
  assert.equal(calls.filter(item => item.tool === "mcp__Claude_Browser__preview_start").length, 0);
});

test("unknown or connection-foreign viewId is rejected before selection", async () => {
  const { $, calls } = host(), state = createModState();
  const id = await observedId($, state);
  const foreign = { ...bridge, token: "b".repeat(64) };
  for (const viewId of ["never-observed", id]) {
    const owner = viewId === id ? foreign : bridge;
    const result = await executeBridgeAction($, state, owner, request("activate-" + viewId, "views.activate", { viewId }));
    assert.equal(result.status, "rejected");
  }
  assert.equal(calls.some(item => item.tool === "mcp__Claude_Browser__tabs_select"), false);
});

test("a successful select without post-call tab observation is pending rather than not-sent", async () => {
  const { $, calls } = host({ after: () => ({ isError: true }) }), state = createModState();
  const id = await observedId($, state);
  await assert.rejects(executeBridgeAction($, state, bridge, request("activate-1", "views.activate", { viewId: id })), error => error.outcome === "unknown");
  assert.equal(calls.filter(item => item.tool === "mcp__Claude_Browser__tabs_select").length, 1);
});

test("nonboolean native active value cannot establish completed activation", async () => {
  const { $ } = host({ after: () => context([{ tabId: "seed", origin: "http://127.0.0.1:10345", isActive: "false" }]) }), state = createModState();
  const id = await observedId($, state);
  await assert.rejects(executeBridgeAction($, state, bridge, request("activate-1", "views.activate", { viewId: id })), error => error.outcome === "unknown");
});

test("explicit host rejection is returned without claiming activation", async () => {
  const { $ } = host({ onSelect: () => ({ denied: true }) }), state = createModState();
  const id = await observedId($, state);
  await assert.rejects(executeBridgeAction($, state, bridge, request("activate-1", "views.activate", { viewId: id })), error => error.outcome === "rejected");
});

test("select reply without an active target is accepted, not completed", async () => {
  const { $, calls } = host({ onSelect: () => ({ result: { content: [{ type: "text", text: "Fronted tab seed." }] } }) });
  const state = createModState(), id = await observedId($, state);
  const result = await executeBridgeAction($, state, bridge, request("activate-1", "views.activate", { viewId: id }));
  assert.deepEqual({ status: result.status, data: result.data }, { status: "accepted", data: { viewId: id, active: false } });
  assert.equal(calls.filter(item => item.tool === "mcp__Claude_Browser__tabs_select").length, 1);
});

test("pre-selection read failure makes no selection request", async () => {
  const { $, calls } = host(), state = createModState();
  const id = await observedId($, state);
  $.tool.call = async input => { calls.push(input); return { isError: true }; };
  await assert.rejects(executeBridgeAction($, state, bridge, request("activate-1", "views.activate", { viewId: id })), error => error.outcome === "not-sent");
  assert.equal(calls.some(item => item.tool === "mcp__Claude_Browser__tabs_select"), false);
});
