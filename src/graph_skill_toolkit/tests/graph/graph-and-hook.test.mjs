import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { afterTool } from "../../apps/graph_canvas/hooks/after-tool.mjs";
import { projectGraph } from "../../apps/graph_canvas/application/projection/graph.mjs";
import { loadSkill } from "../../apps/graph_canvas/application/source/files.mjs";

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

async function hookSandbox(context) {
  const sandbox = await mkdtemp(join(tmpdir(), "graph hook 中文 "));
  context.after(() => rm(sandbox, { recursive: true, force: true }));
  const root = join(sandbox, "skill");
  await mkdir(join(root, "phase"), { recursive: true });
  await writeFile(join(root, "SKILL.md"), "test");
  await writeFile(join(root, "graph.yaml"), "test");
  await writeFile(join(root, "phase", "input.txt"), "input");
  return {
    sandbox, root, canonicalRoot: await realpath(root),
    base: { hook_event_name: "PostToolUse", cwd: sandbox },
    options: { stateDirectory: join(sandbox, "hook state") },
  };
}

function assertGuidance(result, root) {
  assert.equal(result.hookSpecificOutput.hookEventName, "PostToolUse");
  const message = result.hookSpecificOutput.additionalContext;
  assert.ok(message.includes(JSON.stringify(root)));
  assert.match(message, /after this change or runtime use, display the current canvas/);
  assert.doesNotMatch(message, /SKILL\.md|open_in_codex|both views|document|related operation|operation failed/i);
}

test("explicit write inputs identify the owning skill and refresh its baseline", async context => {
  const { root, canonicalRoot, base, options } = await hookSandbox(context);
  const cases = [
    { tool_name: "Write", tool_input: { file_path: join(root, "phase/AGENT.md") } },
    { tool_name: "Edit", tool_input: { file_path: "skill/graph.yaml" } },
    { tool_name: "MultiEdit", tool_input: { edits: [{ path: "skill/phase/AGENT.md" }] } },
    { tool_name: "NotebookEdit", tool_input: { notebook_path: join(root, "phase/notebook.ipynb") } },
    { tool_name: "apply_patch", tool_input: { command: "*** Begin Patch\n*** Update File: skill/phase/AGENT.md\n*** End Patch" } },
    { tool_name: "apply_patch", tool_input: { patch: "*** Begin Patch\n*** Add File: skill/phase/new.md\n*** End Patch" } },
    { tool_name: "apply_patch", tool_input: { cmd: "*** Begin Patch\n*** Delete File: skill/phase/old.md\n*** End Patch" } },
    { tool_name: "apply_patch", tool_input: "*** Begin Patch\n*** Update File: unrelated.md\n*** Move to: skill/phase/moved.md\n*** End Patch" },
  ];
  const shell = { ...base, tool_name: "Bash", cwd: root, tool_input: { command: "ls" } };
  assert.deepEqual(await afterTool(shell, options), {});
  for (const [index, item] of cases.entries()) {
    await writeFile(join(root, "graph.yaml"), `changed by write ${index}\n`);
    assertGuidance(await afterTool({ ...base, ...item }, options), canonicalRoot);
    assert.deepEqual(await afterTool(shell, options), {}, item.tool_name);
  }
  const files = await readdir(options.stateDirectory);
  assert.deepEqual(files, [createHash("sha256").update(canonicalRoot).digest("hex")]);
  assert.match(await readFile(join(options.stateDirectory, files[0]), "utf8"), /^[a-f0-9]{64}$/);
});

test("read-only, recursive and unrelated calls ignore both skill paths and tool responses", async context => {
  const { root, base, options } = await hookSandbox(context);
  const cases = [
    { tool_name: "Read", tool_input: { file_path: join(root, "SKILL.md") } },
    { tool_name: "Read", tool_input: { file_path: join(root, "phase/input.txt") } },
    { tool_name: "Grep", tool_response: { matches: [{ file_path: join(root, "SKILL.md") }] } },
    { tool_name: "Glob", tool_response: { paths: [{ path: join(root, "graph.yaml") }] } },
    ...["LS", "WebFetch", "unknown"].map(tool_name => ({ tool_name, tool_input: { skill_root: root, path: root } })),
    { tool_name: "mcp__gskill__submit_agent_result", tool_input: { checkpoint_ref: "gskill-handoff-v1:x" } },
    { tool_name: "mcp__gskill__compile", tool_input: { file_path: join(root, "SKILL.md") }, tool_response: { skill_root: root } },
    { tool_name: "mcp__graph_skill_canvas__show_graph", tool_input: { skill_root: root } },
    { tool_name: "show_graph", tool_input: { skill_root: root } },
    { tool_name: "mcp__Claude_Browser__preview_start", tool_input: { url: join(root, "SKILL.md") } },
    { tool_name: "mcp__ccd_host__reveal_path", tool_input: { path: root } },
    { tool_name: "mcp__codex_app__open_in_codex", tool_input: { target: { path: root, type: "file" } } },
    { tool_name: "Read", tool_input: { file_path: "unrelated.md" } },
    { tool_name: "Bash", tool_input: { command: "echo skill/graph.yaml" } },
    { tool_name: "Write", hook_event_name: "PreToolUse", tool_input: { file_path: join(root, "SKILL.md") } },
    { tool_name: "Write", tool_response: { file_path: join(root, "SKILL.md") } },
    { tool_name: "Write", tool_input: { skill_root: root, skill_path: root, filename: join(root, "SKILL.md"), workdir: root, cwd: root } },
    { tool_name: "Write", tool_input: { file_path: "unrelated.md" }, tool_response: { file_path: join(root, "SKILL.md") } },
    { tool_name: "Write", tool_input: { file_path: "bad\0path" } },
    { tool_name: "Write", cwd: null, tool_input: { file_path: "skill/graph.yaml" } },
    { tool_name: "Write", cwd: "relative", tool_input: { file_path: "skill/graph.yaml" } },
    { tool_input: { file_path: join(root, "SKILL.md") } },
  ];
  for (const item of cases) assert.deepEqual(await afterTool({ ...base, ...item }, options), {}, item.tool_name);
  for (const tool_name of ["Read", "Grep", "Glob", "LS", "WebFetch", "unknown"]) {
    const event = { ...base, cwd: root, tool_name, get tool_input() { throw new Error("Ignored tool input was inspected."); } };
    assert.deepEqual(await afterTool(event, options), {});
  }
  await assert.rejects(readdir(options.stateDirectory), { code: "ENOENT" });
});

test("runtime calls on a skill trigger without any file change", async context => {
  const { root, canonicalRoot, base, options } = await hookSandbox(context);
  const cases = [
    { tool_name: "mcp__gskill__compile", tool_input: { skill_root: root } },
    { tool_name: "mcp__gskill__run", tool_input: { invocation: { skill_root: "skill" } } },
    { tool_name: "mcp__gskill__inspect", tool_input: { skill_path: join(root, "phase") } },
    { tool_name: "Bash", cwd: root, tool_input: { command: "gskill compile ." } },
    { tool_name: "PowerShell", cwd: root, tool_input: { command: "cd phase; gskill.exe inspect .." } },
    { tool_name: "exec_command", tool_input: { cmd: "gskill run .", workdir: root } },
  ];
  // Each call repeats on an unchanged skill: use, not change, is the signal.
  for (const item of [...cases, ...cases]) assertGuidance(await afterTool({ ...base, ...item }, options), canonicalRoot);
  // Mentioning the CLI is not starting it.
  for (const command of ["echo gskill", "ls gskill-notes", "cat graph.yaml"]) {
    assert.deepEqual(await afterTool({ ...base, tool_name: "Bash", cwd: root, tool_input: { command } }, options), {}, command);
  }
});

test("explicit writes skip every path segment excluded by the skill fingerprint", async context => {
  const { root, base, options } = await hookSandbox(context);
  for (const path of [".cache/x", "phase/.hidden/input", "node_modules/x", "phase/__pycache__/x"]) {
    assert.deepEqual(await afterTool({ ...base, tool_name: "Write", tool_input: { file_path: join(root, path) } }, options), {});
    assert.deepEqual(await afterTool({ ...base, tool_name: "apply_patch", tool_input: `*** Add File: skill/${path}\n` }, options), {});
  }
  await assert.rejects(readdir(options.stateDirectory), { code: "ENOENT" });
});

for (const tool_name of ["Bash", "exec_command", "functions.exec_command", "PowerShell"]) {
  test(`${tool_name} detects only a changed fingerprint after a stored shell baseline`, async context => {
    const { root, canonicalRoot, base, options } = await hookSandbox(context);
    const event = { ...base, tool_name, tool_input: { cmd: "ls; echo '*** Add File: unrelated.md'", workdir: "skill/phase" } };
    assert.deepEqual(await afterTool(event, options), {});
    await writeFile(join(root, "phase/input.txt"), "a longer changed input");
    assertGuidance(await afterTool(event, options), canonicalRoot);
    assert.deepEqual(await afterTool(event, options), {});
    await mkdir(join(root, ".cache"));
    await writeFile(join(root, ".cache/x"), "ignored change");
    assert.deepEqual(await afterTool(event, options), {});
  });
}

test("shell working directories take precedence and fall back only when unresolved", async context => {
  const { root, canonicalRoot, sandbox, base, options } = await hookSandbox(context);
  const event = { ...base, cwd: root, tool_name: "Bash", tool_input: { command: "ls", workdir: sandbox } };
  assert.deepEqual(await afterTool(event, options), {});
  await assert.rejects(readdir(options.stateDirectory), { code: "ENOENT" });
  event.tool_input.workdir = 12;
  assert.deepEqual(await afterTool(event, options), {});
  await writeFile(join(root, "graph.yaml"), "changed fallback root");
  assertGuidance(await afterTool(event, options), canonicalRoot);
  delete event.cwd;
  event.tool_input.workdir = "skill";
  assert.deepEqual(await afterTool(event, options), {});
  event.tool_input.workdir = root;
  await writeFile(join(root, "graph.yaml"), "absolute workdir without event cwd");
  assertGuidance(await afterTool(event, options), canonicalRoot);
});

test("fingerprint and storage failures suppress shell guidance without escaping the hook", async context => {
  const { root, canonicalRoot, sandbox, base, options } = await hookSandbox(context);
  const shell = { ...base, tool_name: "Bash", cwd: root };
  const blocked = join(sandbox, "state-is-a-file");
  await writeFile(blocked, "block mkdir");
  assert.deepEqual(await afterTool(shell, { stateDirectory: blocked }), {});
  // An explicit write is itself the change, so a lost baseline does not hide it.
  assertGuidance(await afterTool({ ...base, tool_name: "Write", tool_input: { path: join(root, "graph.yaml") } }, { stateDirectory: blocked }), canonicalRoot);
  assert.deepEqual(await afterTool(shell, options), {});
  const baseline = join(options.stateDirectory, createHash("sha256").update(await realpath(root)).digest("hex"));
  const previous = await readFile(baseline, "utf8");
  // Directories also count toward the source fingerprint's 10000-entry bound.
  for (let start = 0; start < 10001; start += 100) {
    await Promise.all(Array.from({ length: Math.min(100, 10001 - start) }, (_, index) => mkdir(join(root, `entry-${start + index}`))));
  }
  assert.deepEqual(await afterTool(shell, options), {});
  assert.equal(await readFile(baseline, "utf8"), previous);
  assert.deepEqual(await readdir(options.stateDirectory), [createHash("sha256").update(await realpath(root)).digest("hex")]);
});

test("built hook matches source, persists shell baselines and handles malformed stdin", async context => {
  const { root, canonicalRoot, base, options } = await hookSandbox(context);
  const executable = fileURLToPath(new URL("../../dist/after-tool.mjs", import.meta.url));
  const invoke = event => {
    const actual = spawnSync(process.execPath, [executable], {
      input: JSON.stringify(event), encoding: "utf8", cwd: tmpdir(),
      env: { ...process.env, GRAPH_SKILL_CANVAS_HOOK_STATE_DIRECTORY: options.stateDirectory },
    });
    assert.equal(actual.status, 0);
    assert.equal(actual.stderr, "");
    return JSON.parse(actual.stdout);
  };
  const write = { ...base, tool_name: "Write", tool_input: { file_path: join(root, "SKILL.md") } };
  assert.deepEqual(invoke(write), await afterTool(write, options));
  const shell = { ...base, tool_name: "Bash", cwd: root, tool_input: { command: "ls" } };
  assert.deepEqual(invoke(shell), {});
  await writeFile(join(root, "graph.yaml"), "changed between hook processes");
  assertGuidance(invoke(shell), canonicalRoot);
  assert.deepEqual(invoke(shell), {});
  assert.deepEqual(invoke({ ...write, tool_name: "Read" }), {});
  const malformed = spawnSync(process.execPath, [executable], {
    input: "{", encoding: "utf8",
    env: { ...process.env, GRAPH_SKILL_CANVAS_HOOK_STATE_DIRECTORY: options.stateDirectory },
  });
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
