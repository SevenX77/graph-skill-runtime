import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { afterTool } from "../src/after-tool.mjs";
import { projectGraph } from "../src/project-graph.mjs";
import { loadSkill } from "../src/skill-files.mjs";

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

test("both host hook payloads identify the owning skill and exclude recursive/unrelated calls", async context => {
  const sandbox = await mkdtemp(join(tmpdir(), "graph hook 中文 "));
  context.after(() => rm(sandbox, { recursive: true, force: true }));
  const root = join(sandbox, "skill");
  await mkdir(join(root, "phase"), { recursive: true });
  await writeFile(join(root, "SKILL.md"), "test");
  await writeFile(join(root, "graph.yaml"), "test");
  const base = { hook_event_name: "PostToolUse", cwd: sandbox };
  const cases = [
    { tool_name: "mcp__gskill__compile", tool_input: { skill_root: root } },
    { tool_name: "mcp__gskill__run", tool_input: { invocation: { skill_root: root } } },
    { tool_name: "Write", tool_input: { file_path: join(root, "phase/AGENT.md") } },
    { tool_name: "Read", tool_input: { file_path: join(root, "SKILL.md") } },
    { tool_name: "apply_patch", tool_input: { command: "*** Begin Patch\n*** Update File: skill/phase/AGENT.md\n*** End Patch" } },
    { tool_name: "Bash", cwd: root, tool_input: { command: "gskill compile ." } },
    { tool_name: "exec_command", tool_input: { cmd: "gskill inspect .", workdir: root } },
  ];
  for (const item of cases) {
    const result = await afterTool({ ...base, ...item });
    assert.equal(result.hookSpecificOutput.hookEventName, "PostToolUse");
    assert.ok(result.hookSpecificOutput.additionalContext.includes(JSON.stringify(root)), item.tool_name);
  }
  for (const item of [
    { tool_name: "mcp__graph_skill_canvas__show_graph", tool_input: { skill_root: root } },
    { tool_name: "show_graph", tool_input: { skill_root: root } },
    { tool_name: "mcp__codex_app__open_in_codex", tool_input: { target: { path: root, type: "file" } } },
    { tool_name: "Read", tool_input: { file_path: join(sandbox, "unrelated.md") } },
    { tool_name: "Bash", tool_input: { command: "echo hello" } },
    { tool_name: "Write", hook_event_name: "PreToolUse", tool_input: { file_path: join(root, "SKILL.md") } },
  ]) assert.deepEqual(await afterTool({ ...base, ...item }), {});
  const executable = fileURLToPath(new URL("../dist/after-tool.mjs", import.meta.url));
  const actual = spawnSync(process.execPath, [executable], { input: JSON.stringify({ ...base, ...cases[0] }), encoding: "utf8", cwd: tmpdir() });
  assert.equal(actual.status, 0);
  assert.equal(actual.stderr, "");
  assert.deepEqual(JSON.parse(actual.stdout), await afterTool({ ...base, ...cases[0] }));
  const malformed = spawnSync(process.execPath, [executable], { input: "{", encoding: "utf8" });
  assert.equal(malformed.status, 0);
  assert.deepEqual(JSON.parse(malformed.stdout), {});
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
  assert.equal((await loadSkill(root)).skillRoot, resolve(root));
  await writeFile(join(root, "phases/a/AGENT.md"), "test");
  await assert.rejects(loadSkill(root), /exactly one type file/);
});

test("repository's portable hello-world example renders its real phase", async () => {
  const skill = await loadSkill(fileURLToPath(new URL("../../../examples/hello-world/", import.meta.url)));
  const projected = projectGraph(skill.data, skill.kinds);
  assert.deepEqual(projected.nodes.map(node => node.id), ["input", "greet", "$output"]);
  assert.equal(projected.nodes[1].kind, "LOGIC");
});
