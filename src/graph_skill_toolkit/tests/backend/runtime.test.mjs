import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, writeFile, readFile, rm, readdir, cp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeCompiler, parseCompileResult, runtimeCommand } from "../../backend/runtime/index.mjs";
import { fakeRuntimeCommand } from "../support/runtime.mjs";

const diagnostic = { code: "[F-x]", severity: "fatal", message: "bad", source_path: "graph.yaml", line: 3 };
const result = (status, diagnostics = []) => JSON.stringify({ schema_version: "gskill.compile-result.v1", kind: "compile_result", status, skill_id: null, diagnostics });

test("compile results keep the runtime's diagnostics and reject output outside the contract", () => {
  assert.deepEqual(parseCompileResult(result("passed"), 0), { status: "passed", diagnostics: [] });
  assert.deepEqual(parseCompileResult(result("failed", [diagnostic]), 2), { status: "failed", diagnostics: [diagnostic] });
  assert.throws(() => parseCompileResult("Traceback", 2), /unreadable output/);
  assert.throws(() => parseCompileResult(JSON.stringify({ status: "passed", diagnostics: [] }), 0), /unrecognized result/);
  assert.throws(() => parseCompileResult(result("failed", [{ message: "no code" }]), 2), /unrecognized result/);
  assert.throws(() => parseCompileResult(result("passed"), 2), /disagrees/);
});

test("runtime command comes from an explicit override or the installation record", async t => {
  assert.deepEqual(runtimeCommand({ env: { GRAPH_SKILL_RUNTIME: JSON.stringify(["py", "-m", "x"]) } }), ["py", "-m", "x"]);
  assert.throws(() => runtimeCommand({ env: { GRAPH_SKILL_RUNTIME: JSON.stringify("py") } }), /JSON array/);
  const state = await mkdtemp(join(tmpdir(), "runtime-state-"));
  t.after(() => rm(state, { recursive: true, force: true }));
  assert.throws(() => runtimeCommand({ env: {}, stateRoot: state }), /not installed/);
  await writeFile(join(state, "install.json"), JSON.stringify({ schema: "graph-skill.toolkit-install.v1", release: "0.3.5-0123456789abcdef" }));
  assert.deepEqual(runtimeCommand({ env: {}, stateRoot: state, platform: "win32" }),
    [join(state, "versions", "0.3.5-0123456789abcdef", "runtimes", "python", "python.exe"), "-I", "-B", "-X", "utf8", "-m", "graph_skill_runtime"]);
  await writeFile(join(state, "install.json"), JSON.stringify({ schema: "graph-skill.toolkit-install.v1", release: "../escape" }));
  assert.throws(() => runtimeCommand({ env: {}, stateRoot: state }), /Invalid toolkit installation manifest/);
});

test("the compiler spawns the runtime process and reports start failures, crashes and timeouts", async t => {
  const temp = await mkdtemp(join(tmpdir(), "runtime-spawn-"));
  t.after(() => rm(temp, { recursive: true, force: true }));
  const skill = join(temp, "skill");
  await mkdir(join(skill, "phases", "work"), { recursive: true });
  await writeFile(join(skill, "SKILL.md"), "# Skill\n");
  await writeFile(join(skill, "phases", "work", "LOGIC.md"), "# Logic\n");
  await writeFile(join(skill, "graph.yaml"), "schema_version: gskill.graph.v1\ngraph_id: g\nphases:\n  - id: work\n    depends_on: [input]\n    output: true\n");
  const compiler = createRuntimeCompiler({ command: () => fakeRuntimeCommand });
  assert.deepEqual(await compiler.compile(skill), { status: "passed", diagnostics: [] });
  await writeFile(join(skill, "graph.yaml"), "fake-invalid\n");
  const failed = await compiler.compile(skill);
  assert.equal(failed.status, "failed");
  assert.equal(failed.diagnostics[0].code, "[F-fake-runtime]");
  await assert.rejects(createRuntimeCompiler({ command: () => [join(temp, "missing-python.exe")] }).compile(skill), /could not start/);
  await assert.rejects(createRuntimeCompiler({ command: () => { throw new Error("Graph Skill runtime is not installed (no install.json)."); } }).compile(skill), /not installed/);
  const sleeper = join(temp, "sleep.mjs");
  await writeFile(sleeper, "setTimeout(() => {}, 60000);\n");
  await assert.rejects(createRuntimeCompiler({ command: () => [process.execPath, sleeper], timeoutMs: 200 }).compile(skill), /exceeded 200 ms/);
  const crasher = join(temp, "crash.mjs");
  await writeFile(crasher, "console.error('boom'); process.exit(1);\n");
  await assert.rejects(createRuntimeCompiler({ command: () => [process.execPath, crasher] }).compile(skill), /exit 1: boom/);
});

// Opt-in evidence against the bundled runtime on this machine; an absent runtime is a recorded blind spot.
const installed = (() => { try { return existsSync(runtimeCommand({ env: {} })[0]); } catch { return false; } })();
test("the installed runtime reports compile diagnostics for the example skill", { skip: installed ? false : "No installed Graph Skill runtime on this machine." }, async t => {
  const temp = await mkdtemp(join(tmpdir(), "runtime-real-"));
  t.after(() => rm(temp, { recursive: true, force: true }));
  const skill = join(temp, "hello-world");
  await cp(fileURLToPath(new URL("../../../../examples/hello-world", import.meta.url)), skill, { recursive: true });
  const compiler = createRuntimeCompiler({ command: () => runtimeCommand({ env: {} }) });
  const passed = await compiler.compile(skill);
  assert.equal(passed.status, "passed", JSON.stringify(passed.diagnostics));
  const graph = await readFile(join(skill, "graph.yaml"), "utf8");
  assert.ok(graph.includes("depends_on: [input]"));
  await writeFile(join(skill, "graph.yaml"), graph.replace("depends_on: [input]", "depends_on: [missing]"));
  const failed = await compiler.compile(skill);
  assert.equal(failed.status, "failed");
  assert.ok(failed.diagnostics.some(item => item.source_path === "graph.yaml" && /missing/.test(item.message)), JSON.stringify(failed.diagnostics));
  assert.deepEqual((await readdir(skill)).filter(name => name.startsWith(".")), []);
});
