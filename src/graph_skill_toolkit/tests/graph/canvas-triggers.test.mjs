// The canvas's page-trigger behaviours, through the toolkit's real trigger declaration and Hostpane's public trigger entry.
import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterToolTrigger, parseTriggerFile } from "hostpane/triggers";
import { toolkitTriggers } from "../../composition/triggers.mjs";
import graphSkill from "../../apps/graph_canvas/triggers.json" with { type: "json" };

const plugin = toolkitTriggers();

const sha256 = value => createHash("sha256").update(value).digest("hex");
const baselineName = root => sha256(`plugin\0graph-skill.root\0${root}`);
const afterTool = (event, options) => afterToolTrigger(event, plugin, options);

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
  assert.ok(message.includes(`call show_graph of the graph-skill-canvas MCP server with ${JSON.stringify({ skill_root: root })}`), message);
  assert.ok(message.includes("Follow the graph-skill-canvas skill."));
  assert.doesNotMatch(message, /open_in_codex|both views|related operation|operation failed/i);
}

test("the Graph Skill rule file parses without problems", () => {
  assert.deepEqual(parseTriggerFile(graphSkill, { origin: "plugin", pageTools: ["show_graph"] }).problems, []);
  assert.equal(plugin.rules.length, 1);
  assert.equal(plugin.rules[0].origin, "plugin");
  assert.ok(Object.isFrozen(plugin.rules[0]) && Object.isFrozen(plugin.rules[0].scope.markers));
});

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
  assert.deepEqual((await readdir(options.stateDirectory)).sort(), ["baselines", "firings.jsonl", "roots.json"]);
  const baselines = await readdir(join(options.stateDirectory, "baselines"));
  assert.deepEqual(baselines, [baselineName(canonicalRoot)]);
  assert.match(await readFile(join(options.stateDirectory, "baselines", baselines[0]), "utf8"), /^[a-f0-9]{64}$/);
  const roots = JSON.parse(await readFile(join(options.stateDirectory, "roots.json"), "utf8"));
  assert.equal(roots.schema, "hostpane.trigger-roots.v1");
  assert.deepEqual(roots.roots.map(({ origin, rule, root: entry }) => ({ origin, rule, root: entry })), [{ origin: "plugin", rule: "graph-skill.root", root: canonicalRoot }]);
  const log = (await readFile(join(options.stateDirectory, "firings.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line));
  assert.equal(log.length, cases.length);
  assert.ok(log.every(firing => firing.reason === "write" && firing.root === canonicalRoot));
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
  for (const tool_name of ["Read", "Grep", "Glob", "LS", "WebFetch", "unknown", "mcp__ccd_view__show_pane", "open_skill_folder", "mcp__graph-skill-canvas__show_graph"]) {
    const event = { ...base, cwd: root, tool_name, get tool_input() { throw new Error("Ignored tool input was inspected."); } };
    assert.deepEqual(await afterTool(event, options), {}, tool_name);
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
  for (const item of [...cases, ...cases]) {
    const result = await afterTool({ ...base, ...item }, options);
    assertGuidance(result, canonicalRoot);
    assert.ok(result.hookSpecificOutput.additionalContext.includes(`${item.tool_name} used ${canonicalRoot}`));
  }
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
    const changed = await afterTool(event, options);
    assertGuidance(changed, canonicalRoot);
    assert.ok(changed.hookSpecificOutput.additionalContext.includes(`a ${tool_name} call changed files under ${canonicalRoot}`));
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
  const baseline = join(options.stateDirectory, "baselines", baselineName(await realpath(root)));
  const previous = await readFile(baseline, "utf8");
  // Directories also count toward the source fingerprint's 10000-entry bound.
  for (let start = 0; start < 10001; start += 100) {
    await Promise.all(Array.from({ length: Math.min(100, 10001 - start) }, (_, index) => mkdir(join(root, `entry-${start + index}`))));
  }
  assert.deepEqual(await afterTool(shell, options), {});
  assert.equal(await readFile(baseline, "utf8"), previous);
  assert.deepEqual(await readdir(options.stateDirectory), ["baselines"]);
  assert.deepEqual(await readdir(join(options.stateDirectory, "baselines")), [baselineName(await realpath(root))]);
});
