import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments, failureResult } from "../../../plugin_base/ports/host/contract.mjs";
import { capability as codexCapability } from "../../../plugin_base/host_interfaces/skills/invoke/codex.mjs";
import { capability as claudeCapability } from "../../../plugin_base/host_interfaces/skills/invoke/claude.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";

const root = "C:/business/example";
const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: root };
const request = (id, args) => ({ id, action: "skills.invoke", args, key: root });
const nativeTools = [{ name: "Skill", description: "Activate a Skill", mcp: false }];
function host(reply, tools = nativeTools) {
  const calls = [];
  const $ = {
    session: { id: async () => "session-a" },
    tool: { list: async () => tools, call: async input => { calls.push(input); return typeof reply === "function" ? reply(input) : reply; } },
  };
  return { $, calls };
}
const execute = (api, id, args) => executeBridgeAction(api, createModState(), bridge, request(id, args));

test("Skill input is generic, named, and optional JSON; Codex does not substitute a message", () => {
  assert.deepEqual(validateArguments("skills.invoke", { skill: "example", input: { query: "中文" } }), { skill: "example", input: { query: "中文" } });
  for (const skill of ["", "  ", "one\ntwo"]) assert.throws(() => validateArguments("skills.invoke", { skill }));
  assert.equal(codexCapability().state, "unknown");
  assert.equal(claudeCapability([]).state, "unavailable");
  assert.equal(claudeCapability(nativeTools).state, "available");
});

test("Claude uses the actual flat Skill tool envelope and acknowledges only native activation", async () => {
  const { $, calls } = host({ result: { success: true, commandName: "example", status: "inline" }, text: "loaded" });
  const result = await execute($, "invoke", { skill: "example", input: "run this" });
  assert.deepEqual(calls, [{ tool: "Skill", skill: "example", args: "run this" }]);
  assert.equal(result.status, "completed");
  assert.match(result.message, /业务任务结果须另行核对/);
  assert.equal(result.data.result.commandName, "example");
});

test("Claude does not coerce JSON input or call the host without a listed Skill tool", async () => {
  const a = host({ result: { success: true, commandName: "example" } });
  assert.equal((await execute(a.$, "object", { skill: "example", input: { id: 1 } })).status, "unsupported");
  assert.deepEqual(a.calls, []);
  const b = host(null, []);
  assert.equal((await execute(b.$, "unlisted", { skill: "example" })).status, "unsupported");
  assert.deepEqual(b.calls, []);
});

test("Claude distinguishes refused, failed, read-only, background and missing activation receipts", async () => {
  for (const [response, status, pattern] of [
    [{ deny: "Denied" }, "rejected", /拒绝/],
    [{ isError: true, text: "not found" }, "error", /返回错误/],
    [{ result: { success: false, commandName: "missing" } }, "error", /激活失败/],
    [{ result: { success: true, commandName: "example", status: "inline", readOnly: true } }, "completed", /只读加载/],
    [{ result: { success: true, commandName: "example", status: "forked", agentId: "agent-1", result: "launched", background: true } }, "accepted", /业务结果仍待/],
    [{ result: { ok: true } }, "pending", /不要重试/],
  ]) {
    const { $, calls } = host(response);
    const result = response.deny
      ? await execute($, "case", { skill: "example" }).catch(error => failureResult(error, true))
      : await execute($, "case", { skill: "example" });
    assert.equal(result.status, status);
    assert.match(result.message, pattern);
    assert.deepEqual(calls, [{ tool: "Skill", skill: "example" }]);
  }
});

test("lost native reply is not silently reported as activation or resent", async () => {
  const { $, calls } = host(() => { throw new Error("receipt lost"); });
  const result = await execute($, "lost", { skill: "example" }).catch(error => failureResult(error, true));
  assert.equal(result.status, "pending");
  assert.match(result.message, /receipt lost/);
  assert.equal(calls.length, 1);
});
