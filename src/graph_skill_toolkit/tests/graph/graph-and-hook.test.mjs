import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, readFile, rm, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parseTriggerFile } from "hostpane/triggers";
import { projectGraph } from "../../apps/graph_canvas/application/projection/graph.mjs";
import { loadSkill } from "../../apps/graph_canvas/application/source/files.mjs";
import { toolkitTriggers, toolkitTriggersAt } from "../../composition/triggers.mjs";

test("actual branched graph projection preserves edges and separates siblings", () => {
  const phase = (id, depends_on, output = false) => ({ id, depends_on, output });
  const phases = [phase("a", ["input"]), phase("b", ["input"]), phase("merge", ["a", "b"], true)];
  const projected = projectGraph({ graph_id: "branch", phases }, { a: "AGENT", b: "SUBGRAPH", merge: "LOGIC" });
  assert.deepEqual(projected.edges, [{ from: "input", to: "a" }, { from: "input", to: "b" }, { from: "a", to: "merge" }, { from: "b", to: "merge" }, { from: "merge", to: "$output" }]);
  assert.equal(projected.nodes[1].y, projected.nodes[2].y);
  assert.notEqual(projected.nodes[1].x, projected.nodes[2].x);
  for (const invalid of [[phase("a", ["missing"], true)], [phase("a", ["a"], true)], [phase("a", ["input"]), phase("A", ["input"], true)]]) {
    assert.throws(() => projectGraph({ graph_id: "bad", phases: invalid }, {}));
  }
});

const toolkitRoot = fileURLToPath(new URL("../../", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("../../../../", import.meta.url));
const builtHook = join(toolkitRoot, "dist", "after-tool.mjs");

/** Runs the built hook as a host would: the event on standard input, guidance or {} on standard output. */
function invokeHook(event, stateDirectory) {
  const actual = spawnSync(process.execPath, [builtHook], {
    input: typeof event === "string" ? event : JSON.stringify(event), encoding: "utf8", cwd: tmpdir(),
    env: { ...process.env, HOSTPANE_TRIGGER_STATE_DIRECTORY: stateDirectory },
  });
  assert.equal(actual.status, 0, actual.stderr);
  return JSON.parse(actual.stdout);
}

test("the toolkit declares its page tool and rule", () => {
  const canvas = toolkitTriggers();
  assert.deepEqual([canvas.name, canvas.pageTools, canvas.rules.map(rule => rule.id)], ["graph-skill-canvas", ["show_graph"], ["graph-skill.root"]]);
  // A source build names its own folder for the rebuild step; a folder without the toolkit's manifest names none.
  assert.deepEqual(toolkitTriggersAt(join(toolkitRoot, "dist")).source, { root: resolve(toolkitRoot), build: "npm run build" });
  assert.equal(toolkitTriggersAt(tmpdir()).source, null);
});

test("this repository's project rules are valid for the toolkit's page tools", async () => {
  const file = join(repositoryRoot, ".hostpane", "triggers.json");
  const parsed = parseTriggerFile(JSON.parse(await readFile(file, "utf8")), { origin: file, pageTools: ["show_graph"], plugin: "graph-skill-canvas" });
  assert.deepEqual(parsed.problems, []);
  assert.deepEqual(parsed.rules.map(rule => rule.id), ["graph-canvas.source", "toolkit.shared"]);
});

test("the built hook asks for the canvas after a Graph Skill write and ignores reads and bad input", async context => {
  const sandbox = await mkdtemp(join(tmpdir(), "graph hook 中文 "));
  context.after(() => rm(sandbox, { recursive: true, force: true }));
  const skill = join(sandbox, "skill");
  await mkdir(join(skill, "phase"), { recursive: true });
  await writeFile(join(skill, "SKILL.md"), "test");
  await writeFile(join(skill, "graph.yaml"), "test");
  const state = join(sandbox, "state");
  const write = { hook_event_name: "PostToolUse", cwd: sandbox, tool_name: "Edit", tool_input: { file_path: join(skill, "graph.yaml") } };
  const message = invokeHook(write, state).hookSpecificOutput.additionalContext;
  assert.ok(message.includes(`call show_graph of the graph-skill-canvas MCP server with ${JSON.stringify({ skill_root: await realpath(skill) })}`), message);
  assert.match(message, /Follow the graph-skill-canvas skill\./);
  assert.doesNotMatch(message, /npm run build/);
  assert.deepEqual(invokeHook({ ...write, tool_name: "Read" }, state), {});
  assert.deepEqual(invokeHook({ ...write, tool_name: "mcp__graph-skill-canvas__show_graph" }, state), {});
  assert.deepEqual(invokeHook("{", state), {});
});

test("the built hook opens the canvas and rebuilds after an edit of the canvas source in this repository", async context => {
  const state = await mkdtemp(join(tmpdir(), "graph hook state "));
  context.after(() => rm(state, { recursive: true, force: true }));
  const file = join(toolkitRoot, "apps", "graph_canvas", "ui", "workbench", "index.tsx");
  const message = invokeHook({ hook_event_name: "PostToolUse", cwd: repositoryRoot, tool_name: "Edit", tool_input: { file_path: file } }, state).hookSpecificOutput.additionalContext;
  assert.match(message, /Rule graph-canvas\.source \(画布源码\), Edit wrote .*: call show_graph of the graph-skill-canvas MCP server with \{"skill_root":".*hello-world"\}\./);
  assert.match(message, /run `npm run build` there first/);
  assert.doesNotMatch(message, /open_interface_lab/);
});

test("Skill loader rejects malformed graphs and ambiguous phase type files", async context => {
  const root = await mkdtemp(join(tmpdir(), "graph malformed "));
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(join(root, "SKILL.md"), "test");
  await writeFile(join(root, "graph.yaml"), "phases: [");
  await assert.rejects(loadSkill(root));
  await mkdir(join(root, "phases", "a"), { recursive: true });
  await writeFile(join(root, "graph.yaml"), "schema_version: gskill.graph.v1\ngraph_id: test\nphases:\n  - id: a\n    depends_on: [input]\n    output: true\n");
  await writeFile(join(root, "phases/a/LOGIC.md"), "test");
  assert.equal((await loadSkill(root)).skillRoot, await realpath(root));
  await writeFile(join(root, "phases/a/AGENT.md"), "test");
  await assert.rejects(loadSkill(root), /exactly one type file/);
});

test("repository's portable hello-world example renders its real phase", async () => {
  const skill = await loadSkill(fileURLToPath(new URL("../../../../examples/hello-world", import.meta.url)));
  const projected = projectGraph(skill.data, skill.kinds);
  assert.deepEqual(projected.nodes.map(node => node.id), ["input", "greet", "$output"]);
  assert.equal(projected.nodes[1].kind, "LOGIC");
});
