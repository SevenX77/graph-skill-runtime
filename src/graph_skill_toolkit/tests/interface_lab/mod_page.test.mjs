import assert from "node:assert/strict";
import test from "node:test";
import { labPayload } from "../../apps/interface_lab/claude_mod/page.js";

const payload = { lab: { sandbox: "C:/lab/sandbox" }, presentation: { kind: "http" } };

test("the Mod reads the lab payload in every shape the Claude host delivers", () => {
  // The live host passes the structured content as a JSON string.
  assert.deepEqual(labPayload({ result: JSON.stringify(payload) }), payload);
  assert.deepEqual(labPayload({ result: { structuredContent: payload } }), payload);
  assert.deepEqual(labPayload({ result: payload }), payload);
  assert.deepEqual(labPayload({ result: { content: [{ type: "text", text: JSON.stringify(payload) }] } }), payload);
  assert.throws(() => labPayload({ result: JSON.stringify({ other: 1 }) }), /no Interface Lab data/);
});
