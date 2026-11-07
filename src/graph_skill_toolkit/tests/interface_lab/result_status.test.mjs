import assert from "node:assert/strict";
import test from "node:test";
import { hostLabel, snapshotHost, permissionModeLabel } from "../../apps/interface_lab/application/result_status/index.mjs";

function host(id, version) {
  return { id, status: "confirmed", name: "reported client", version, sessionId: null, transport: id === "codex" ? "mcp-app" : "http-bridge", capabilities: {} };
}

test("a call retains its own host identity and never guesses an unconfirmed host", () => {
  const info = host("claude", "2.1.250");
  const captured = snapshotHost(info);
  info.version = "2.1.251";
  assert.equal(hostLabel(captured), "Claude Code 2.1.250");
  assert.equal(hostLabel({ ...captured, id: "unknown", status: "unknown" }), "未确认宿主");
  assert.equal(hostLabel({ ...captured, version: null }), "Claude Code 版本未知");
});

test("the lab names each mode and shows an unread mode as unknown", () => {
  assert.equal(permissionModeLabel("auto"), "自动");
  assert.equal(permissionModeLabel("default"), "手动");
  assert.equal(permissionModeLabel("bypassPermissions"), "跳过权限确认");
  assert.equal(permissionModeLabel(null), "未知");
  assert.equal(permissionModeLabel("newMode"), "newMode");
  assert.equal(permissionModeLabel("constructor"), "constructor");
});
