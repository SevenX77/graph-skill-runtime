import assert from "node:assert/strict";
import { test } from "node:test";
import { validateInvalidEvent } from "../../ui/diagnostics/index.mjs";
import { describeDiagnostics } from "../../application/graph/service/index.mjs";

const item = n => ({ code: `[F-${n}]`, severity: "fatal", message: `problem ${n}`, source_path: "graph.yaml", line: n, field_path: "phases", extra: "dropped" });

test("page diagnostics keep the runtime's text, bound the list and reject malformed events", () => {
  const value = validateInvalidEvent({ skillRoot: "C:/skill", diagnostics: Array.from({ length: 60 }, (_, i) => item(i + 1)) });
  assert.equal(value.total, 60);
  assert.equal(value.diagnostics.length, 50);
  assert.deepEqual(value.diagnostics[0], { code: "[F-1]", severity: "fatal", message: "problem 1", source_path: "graph.yaml", line: 1, field_path: "phases" });
  assert.equal(validateInvalidEvent({ skillRoot: "C:/skill", diagnostics: [{ code: "c", severity: "fatal", message: "m", line: 0 }] }).diagnostics[0].line, null);
  assert.throws(() => validateInvalidEvent({ diagnostics: [] }), /Skill path/);
  assert.throws(() => validateInvalidEvent({ skillRoot: "C:/skill", diagnostics: [{ message: "m" }] }), /diagnostic/);
});

test("agent-facing text lists each diagnostic with its location", () => {
  assert.equal(describeDiagnostics([item(2), { code: "[F-y]", severity: "fatal", message: "no place" }]), "[F-2] problem 2 (graph.yaml:2)\n[F-y] no place");
});
