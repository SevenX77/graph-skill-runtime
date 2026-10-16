import assert from "node:assert/strict";
import test from "node:test";
import { validateArguments, failureResult } from "../../../plugin_base/ports/host/contract.mjs";
import { capability as codexCapability } from "../../../plugin_base/host_interfaces/skills/invoke/codex.mjs";
import { capability as claudeCapability } from "../../../plugin_base/host_interfaces/skills/invoke/claude.mjs";
import { createModState } from "../../../plugin_base/adapters/claude/mod/lifecycle/index.mjs";
import { executeBridgeAction } from "../../../plugin_base/adapters/claude/mod/operations/index.mjs";

const bridge = { url: "http://127.0.0.1:12345", token: "a".repeat(64), key: "page" };
function host(reply) {
  const sends = [];
  const api = { session: { id: async () => "session-a" }, tool: { list: async () => [], call: assert.fail },
    prompt: { submit: async input => { sends.push(input); return typeof reply === "function" ? reply(input) : reply; } } };
  return { api, sends };
}
const execute = (api, args) => executeBridgeAction(api, createModState(), bridge, { id: "invoke", action: "skills.invoke", args, key: bridge.key });

test("Skill input remains named optional JSON; Claude slash submission is independent of the Skill tool", () => {
  assert.deepEqual(validateArguments("skills.invoke", { skill: "example", input: { query: "中文" } }), { skill: "example", input: { query: "中文" } });
  for (const skill of ["", "  ", "one\ntwo"]) assert.throws(() => validateArguments("skills.invoke", { skill }));
  assert.equal(codexCapability().state, "unknown");
  assert.equal(claudeCapability([]).state, "available");
});

test("Claude skills.invoke submits /name input and reports acceptance rather than hidden activation", async () => {
  const { api, sends } = host(input => ({ text: input.text }));
  const result = await execute(api, { skill: "example", input: "run this" });
  assert.deepEqual(sends, [{ text: "/example run this" }]);
  assert.equal(result.status, "accepted");
  assert.deepEqual(result.evidence.receipt, { text: "/example run this" });
  assert.match(result.message, /对话.*turn.completed/);
  for (const input of [undefined, ""]) {
    const result = await execute(api, { skill: "example", ...(input === undefined ? {} : { input }) });
    assert.equal(result.status, "accepted"); assert.deepEqual(sends.at(-1), { text: "/example" });
  }
});

test("Claude refuses non-string Skill input without coercion or submission", async () => {
  const { api, sends } = host({ text: "unused" });
  assert.equal((await execute(api, { skill: "example", input: { id: 1 } })).status, "unsupported");
  assert.deepEqual(sends, []);
});

test("Claude Skill command reports a prompt drop or missing receipt without claiming activation", async () => {
  const dropped = host({ drop: "blocked" });
  const result = await execute(dropped.api, { skill: "example" });
  assert.equal(result.status, "rejected"); assert.equal(result.evidence.receipt.drop, "blocked");
  const ambiguous = host({});
  await assert.rejects(execute(ambiguous.api, { skill: "example" }), /回执无法确认/);
  assert.equal(ambiguous.sends.length, 1);
});

test("lost Skill submit reply stays unknown and is never replayed", async () => {
  const { api, sends } = host(() => { throw new Error("receipt lost"); });
  const result = await execute(api, { skill: "example" }).catch(error => failureResult(error, true));
  assert.equal(result.status, "pending"); assert.match(result.message, /receipt lost/); assert.equal(sends.length, 1);
});
