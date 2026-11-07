import assert from "node:assert/strict";
import test from "node:test";
import { callSignal, connectionStatus } from "../../apps/interface_lab/application/connection_status/index.mjs";
import { snapshotHost } from "../../apps/interface_lab/application/result_status/index.mjs";

const host = (id = "codex", version = "26.1023.51421") => ({
  id, status: "confirmed", name: id === "codex" ? "ChatGPT" : "Claude Code", version,
  clientType: null, sessionId: null, transport: id === "codex" ? "mcp-app" : "http-bridge",
  identitySource: "mcp-initialize", reason: "", capabilities: {},
});
const available = { state: "available", detail: "宿主声明可用。" };
const connection = {};
const input = (calls = [], extra = {}) => ({ operation: "files.openFile", kind: "host", connected: true,
  connection, host: host(), capability: available, localAvailable: false, calls, ...extra });
const call = (status, extras = {}) => ({ op: "files.openFile", connection, host: snapshotHost(host()),
  result: { status, message: status }, verdict: "", ...extras });

test("before any test the interface is untested, and only a declared outage is red", () => {
  assert.equal(connectionStatus(input()).code, "untested");
  assert.equal(connectionStatus(input([], { capability: { state: "unknown", detail: "尚未声明。" } })).code, "untested");
  assert.equal(connectionStatus(input([], { connected: false })).code, "untested");
  assert.equal(connectionStatus(input([], { host: { ...host(), id: "unknown", status: "unknown", reason: "身份变更" } })).code, "untested");
  assert.equal(connectionStatus(input([], { capability: { state: "unavailable", detail: "没有文件扩展。" } })).code, "failure");
  assert.equal(connectionStatus(input([call("completed")], { capability: { state: "unavailable", detail: "能力已撤回。" } })).code, "failure");
});

test("yellow means a test is open: running, waiting for a receipt, or waiting for a person", () => {
  assert.equal(connectionStatus(input([], { running: "files.openFile" })).tone, "unknown");
  assert.equal(connectionStatus(input([call("completed")], { running: "files.openFile" })).code, "testing");
  assert.equal(connectionStatus(input([call("completed")], { running: "tools.call" })).code, "success");
  assert.equal(connectionStatus(input([call("accepted")])).code, "testing");
  assert.equal(connectionStatus(input([call("pending")])).code, "testing");
});

test("a closed test is green or red", () => {
  for (const status of ["completed"]) assert.equal(connectionStatus(input([call(status)])).tone, "available");
  for (const status of ["rejected", "unsupported", "error"]) assert.equal(connectionStatus(input([call(status)])).tone, "unavailable");
  assert.equal(connectionStatus(input([call("accepted", { verdict: "matches" })])).tone, "available");
  assert.equal(connectionStatus(input([call("accepted", { verdict: "differs" })])).tone, "unavailable");
  assert.equal(connectionStatus(input([call("accepted", { verdict: "not-observed" })])).tone, "unavailable");
  assert.equal(connectionStatus(input([call("completed", { verdict: "differs" })])).tone, "unavailable");
});

test("the latest call decides, so a refusal after a success shows the refusal", () => {
  assert.equal(connectionStatus(input([call("rejected"), call("completed")])).code, "failure");
  assert.equal(connectionStatus(input([call("completed"), call("rejected")])).code, "success");
  assert.equal(connectionStatus(input([call("accepted"), call("accepted", { verdict: "matches" })])).code, "testing");
});

test("a person may accept an expected refusal", () => {
  assert.equal(connectionStatus(input([call("rejected", { verdict: "matches" })])).code, "success");
});

test("the record and the interface read one call the same way", () => {
  for (const item of [call("completed"), call("accepted"), call("rejected"), call("unsupported"), call("error"), call("accepted", { verdict: "matches" })]) {
    assert.deepEqual(connectionStatus(input([item])), callSignal(item));
  }
});

test("calls from another host, session or connection never count", () => {
  const old = call("completed", { host: snapshotHost(host("claude", "2.1.295")) });
  const otherSession = call("completed", { host: { ...snapshotHost(host()), sessionId: "other" } });
  const previous = call("completed", { connection: {} });
  assert.equal(connectionStatus(input([old, otherSession, previous])).code, "untested");
  assert.equal(connectionStatus(input([previous, call("rejected")])).code, "failure");
});

test("local capability status uses its own route even when host identity is unknown", () => {
  const local = { operation: "local.files.read", kind: "local", connected: true, host: null,
    connection, capability: undefined, localAvailable: true, calls: [] };
  assert.equal(connectionStatus(local).code, "untested");
  assert.equal(connectionStatus({ ...local, localAvailable: false }).code, "failure");
  assert.equal(connectionStatus({ ...local, calls: [{ ...call("completed"), op: "local.files.read" }] }).code, "success");
  assert.equal(connectionStatus({ ...local, calls: [{ ...call("completed"), op: "local.files.read", connection: {} }] }).code, "untested");
});
