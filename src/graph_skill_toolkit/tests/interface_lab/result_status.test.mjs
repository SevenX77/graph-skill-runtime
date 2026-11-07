import assert from "node:assert/strict";
import test from "node:test";
import { hostLabel, snapshotHost } from "../../apps/interface_lab/application/result_status/index.mjs";

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
