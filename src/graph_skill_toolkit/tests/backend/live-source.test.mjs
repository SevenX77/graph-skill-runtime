import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createLiveGraphSource } from "../../apps/graph_canvas/application/live_source/index.mjs";
import { readGraphState } from "../../apps/graph_canvas/application/service/index.mjs";
import { fakeCompiler } from "../support/runtime.mjs";

const yaml = id => `schema_version: gskill.graph.v1\ngraph_id: ${id}\nphases:\n  - id: work\n    depends_on: [input]\n    output: true\n`;
async function skill(t) {
  const root = await mkdtemp(join(tmpdir(), "live-source-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "phases", "work"), { recursive: true });
  await writeFile(join(root, "SKILL.md"), "# Skill\n");
  await writeFile(join(root, "phases", "work", "LOGIC.md"), "# Logic\n");
  await writeFile(join(root, "graph.yaml"), yaml("one"));
  return root;
}
async function until(condition) {
  for (let i = 0; i < 200 && !condition(); i++) await new Promise(resolve => setTimeout(resolve, 10));
  assert.ok(condition(), "Expected live source update did not arrive.");
}
const counting = () => {
  const compiler = { compiles: 0, compile: async value => { compiler.compiles++; return fakeCompiler.compile(value); } };
  return compiler;
};

test("the fingerprint gates compiles: unchanged files are not recompiled, phase-file edits are", async t => {
  const root = await skill(t);
  const compiler = counting();
  const source = createLiveGraphSource({ read: value => readGraphState(value, { compiler }), debounceMs: 5, reconcileMs: 20 });
  t.after(() => source.close());
  const events = [];
  const off = source.subscribe(root, event => events.push(event));
  await until(() => events.length === 1);
  await new Promise(resolve => setTimeout(resolve, 150));
  assert.equal(compiler.compiles, 1);
  await writeFile(join(root, "phases", "work", "LOGIC.md"), "# Logic, edited\n");
  await until(() => compiler.compiles === 2);
  off();
});

test("invalid files yield the runtime diagnostics, recovery yields a snapshot, and selection failures are errors", async t => {
  const root = await skill(t);
  const source = createLiveGraphSource({ read: value => readGraphState(value, { compiler: fakeCompiler }), debounceMs: 5, reconcileMs: 10000 });
  t.after(() => source.close());
  assert.equal((await source.current(root)).data.graph.id, "one");
  await writeFile(join(root, "graph.yaml"), "broken");
  const invalid = await source.current(root);
  assert.equal(invalid.type, "invalid");
  assert.equal(invalid.diagnostics[0].code, "[F-test]");
  await writeFile(join(root, "graph.yaml"), yaml("two"));
  assert.equal((await source.current(root)).data.graph.id, "two");
  assert.equal((await source.current(join(root, "missing"))).type, "error");
});

test("a root outlives its last listener for the retention window and reuses that compile", async t => {
  const root = await skill(t);
  const compiler = counting();
  const source = createLiveGraphSource({ read: value => readGraphState(value, { compiler }), reconcileMs: 10000, retainMs: 100 });
  t.after(() => source.close());
  await source.current(root);
  const events = [];
  const off = source.subscribe(root, event => events.push(event));
  await until(() => events.length === 1);
  assert.equal(compiler.compiles, 1);
  off();
  await new Promise(resolve => setTimeout(resolve, 250));
  await source.current(root);
  assert.equal(compiler.compiles, 2);
});

test("a runtime that cannot compile becomes an error event naming the cause", async t => {
  const root = await skill(t);
  const compiler = { compile: async () => { throw new Error("Graph Skill runtime could not start: ENOENT"); } };
  const source = createLiveGraphSource({ read: value => readGraphState(value, { compiler }), reconcileMs: 10000 });
  t.after(() => source.close());
  assert.deepEqual(await source.current(root), { type: "error", message: "Graph Skill runtime could not start: ENOENT" });
});
