import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { mcpConnection } from "../../../../plugin_base/adapters/codex/connection/index.mjs";
import { codexAdapter } from "../../../../plugin_base/adapters/codex/driver/index.mjs";
import { capability } from "../../../../plugin_base/host_interfaces/skills/invoke/codex.mjs";
import { failureResult, validateArguments, validateResult } from "../../../../plugin_base/ports/host/contract.mjs";

// These in-memory protocol peers verify request and receipt semantics only.
// They do not establish Skill discovery or activation in a real Codex session.
const action = "skills.invoke";
function pair() {
  const left = { start: async () => {} }, right = { start: async () => {} };
  left.send = async value => queueMicrotask(() => right.onmessage?.(value));
  right.send = async value => queueMicrotask(() => left.onmessage?.(value));
  left.close = async () => left.onclose?.();
  right.close = async () => right.onclose?.();
  return { left, right };
}

function fixture(reply = {}) {
  const sent = [];
  const app = { getHostCapabilities: () => ({ message: { text: {} } }), sendMessage: async params => {
    sent.push(params);
    return typeof reply === "function" ? reply(params) : reply;
  } };
  return { app, sent, driver: codexAdapter(app) };
}

test("Codex Skill request capability requires an actual text capability declaration", async () => {
  for (const host of [{}, { message: {} }, { message: { image: {} } }, ...[null, false, true, [], "text"].map(text => ({ message: { text } }))]) {
    assert.equal(capability(host).state, "unavailable");
    const { app, sent } = fixture();
    app.getHostCapabilities = () => host;
    assert.equal((await codexAdapter(app).invoke(action, { skill: "example" })).status, "unsupported");
    assert.deepEqual(sent, []);
  }
  const declared = capability({ message: { text: {} } });
  assert.equal(declared.state, "available");
  assert.equal(declared.scope, "skill-activation-request");
  assert.deepEqual(declared.constraints.inputTypes, ["string"]);
  assert.match(declared.limits.join(" "), /宿主自行定位技能.*回执只确认请求受理/);
});

test("Codex SDK sends one ui/message Skill marker and reports receipt acceptance only", async t => {
  const { left, right } = pair();
  const bridge = new AppBridge(null, { name: "chatgpt", version: "test" }, { message: { text: {} } });
  const app = new App({ name: "Skill request protocol test", version: "0.0.0" }, {}, { autoResize: false });
  const connection = mcpConnection(app, { transport: left });
  t.after(async () => { await connection.dispose(); await bridge.close(); });
  const received = [];
  let reject = false;
  bridge.onmessage = async params => { received.push(params); return reject ? { isError: true } : {}; };
  await bridge.connect(right);
  await connection.connect({ receive() {}, fail: assert.fail });
  const driver = codexAdapter(app);
  assert.equal((await connection.inspect()).capabilities[action].state, "available");
  const args = validateArguments(action, { skill: "example", input: "保留输入 ✓\n第二行" });
  const result = validateResult(await driver.invoke(action, args));
  const params = { role: "user", content: [{ type: "text", text: "$example 保留输入 ✓\n第二行" }] };
  assert.deepEqual(received, [params]);
  assert.deepEqual(result.evidence.sent, params);
  assert.deepEqual(result.evidence.receipt, {});
  assert.equal(result.status, "accepted");
  assert.match(result.message, /是否找到、激活及执行结果需在对话中核对/);
  assert.equal(result.evidence.observed, undefined);
  reject = true;
  const error = await driver.invoke(action, { skill: "example" });
  assert.equal(error.status, "error");
  assert.deepEqual(error.evidence.receipt, { isError: true });
  assert.equal(received.length, 2);
});

test("Codex Skill input preserves supported names and optional string input exactly", async () => {
  const { driver, sent } = fixture({ isError: false });
  for (const skill of ["example", "skill-name_2", "spreadsheets:Spreadsheets", "a".repeat(256)]) {
    for (const input of [undefined, "", "  keep spaces  "]) {
      const result = await driver.invoke(action, { skill, ...(input === undefined ? {} : { input }) });
      assert.equal(result.status, "accepted");
      assert.deepEqual(sent.at(-1), { role: "user", content: [{ type: "text", text: "$" + skill + (input ? " " + input : "") }] });
    }
  }
});

test("Codex refuses non-string Skill input without conversion or submission", async () => {
  const { driver, sent } = fixture();
  for (const input of [null, false, 0, [], { query: "task" }]) {
    const result = await driver.invoke(action, validateArguments(action, { skill: "example", input }));
    assert.equal(result.status, "unsupported");
    assert.equal(result.evidence.sent, null);
  }
  assert.deepEqual(sent, []);
});

test("Codex refuses skill identifiers that could add text or malformed markers", async () => {
  const { driver, sent } = fixture();
  for (const skill of [undefined, null, 4, "", " example", "example ", "one two", "one\ntwo", "one\ttwo", "one\0two", "$example", "/example", "../example", "a:b:c", ":example", "example:", "a".repeat(257)]) {
    const result = await driver.invoke(action, { skill });
    assert.equal(result.status, "unsupported", JSON.stringify(skill));
    assert.equal(result.evidence.sent, null);
  }
  assert.deepEqual(sent, []);
});

test("ambiguous Codex Skill receipts remain pending and are not retried", async () => {
  for (const receipt of [undefined, null, true, "accepted", [], { isError: "false" }]) {
    const { driver, sent } = fixture(() => receipt);
    const result = await driver.invoke(action, { skill: "example" }).catch(error => failureResult(error, true));
    assert.equal(result.status, "pending");
    assert.match(result.message, /回执无法确认/);
    assert.equal(sent.length, 1);
  }
  const { driver, sent } = fixture(() => { throw new Error("receipt lost"); });
  const result = await driver.invoke(action, { skill: "example" }).catch(error => failureResult(error, true));
  assert.equal(result.status, "pending");
  assert.match(result.message, /receipt lost/);
  assert.equal(sent.length, 1);
});

test("explicit Codex Skill rejection remains rejected without activation claims or retries", async () => {
  for (const detail of [{ outcome: "rejected" }, { code: -32600 }, { code: -32601 }, { code: -32602 }]) {
    const { driver, sent } = fixture(() => { throw Object.assign(new Error("host refused"), detail); });
    const result = await driver.invoke(action, { skill: "example" }).catch(error => failureResult(error, true));
    assert.equal(result.status, "rejected");
    assert.equal(sent.length, 1);
  }
});
