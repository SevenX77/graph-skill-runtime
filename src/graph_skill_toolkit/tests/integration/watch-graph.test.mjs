import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, writeFile, rm, realpath, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { fakeRuntimeEnv } from "../support/runtime.mjs";

const graphYaml = id => `schema_version: gskill.graph.v1\ngraph_id: ${id}\nphases:\n  - id: process\n    depends_on: [input]\n    output: true\n`;

test("real stdio watch_graph long-polls the selected root and returns a saved change without another show_graph", async t => {
  const temp = await realpath(await mkdtemp(join(tmpdir(), "watch graph 中文 ")));
  t.after(() => rm(temp, { recursive: true, force: true }));
  const skill = join(temp, "skill");
  await mkdir(join(skill, "phases", "process"), { recursive: true });
  await writeFile(join(skill, "SKILL.md"), "---\nname: test\n---\n");
  await writeFile(join(skill, "phases", "process", "LOGIC.md"), "# Logic\n");
  await writeFile(join(skill, "graph.yaml"), graphYaml("before"));
  const client = new Client({ name: "watch-graph-test", version: "1" });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [fileURLToPath(new URL("../../dist/server.mjs", import.meta.url))], stderr: "pipe", env: fakeRuntimeEnv() }));
  t.after(() => client.close());

  const tool = (await client.listTools()).tools.find(item => item.name === "watch_graph");
  assert.deepEqual(tool._meta.ui, { visibility: ["app"] });
  assert.equal(tool.annotations.readOnlyHint, true);
  const refused = await client.callTool({ name: "watch_graph", arguments: { skill_root: skill, timeout_ms: 10 } });
  assert.equal(refused.isError, true);
  assert.match(refused.content[0].text, /show_graph/);

  assert.notEqual((await client.callTool({ name: "show_graph", arguments: { skill_root: skill } })).isError, true);
  const first = await client.callTool({ name: "watch_graph", arguments: { skill_root: skill, timeout_ms: 5000 } });
  assert.equal(first.structuredContent.event.type, "snapshot");
  assert.equal(first.structuredContent.event.data.graph.id, "before");
  const revision = first.structuredContent.revision;
  assert.deepEqual((await client.callTool({ name: "watch_graph", arguments: { skill_root: skill, after_revision: revision, timeout_ms: 30 } })).structuredContent, { revision, event: null });

  const pending = client.callTool({ name: "watch_graph", arguments: { skill_root: skill, after_revision: revision, timeout_ms: 10000 } });
  await new Promise(resolve => setTimeout(resolve, 100));
  await writeFile(join(skill, "graph.yaml"), graphYaml("after"));
  const changed = await pending;
  assert.equal(changed.structuredContent.event.type, "snapshot");
  assert.equal(changed.structuredContent.event.data.graph.id, "after");
  assert.ok(changed.structuredContent.revision > revision);
  assert.equal(await readFile(join(skill, "SKILL.md"), "utf8"), "---\nname: test\n---\n");
});

test("real stdio show_graph opens an invalid graph with runtime diagnostics, and a valid save redraws over watch_graph", async t => {
  const temp = await realpath(await mkdtemp(join(tmpdir(), "watch invalid ")));
  t.after(() => rm(temp, { recursive: true, force: true }));
  const skill = join(temp, "skill");
  await mkdir(join(skill, "phases", "process"), { recursive: true });
  await writeFile(join(skill, "SKILL.md"), "---\nname: test\n---\n");
  await writeFile(join(skill, "phases", "process", "LOGIC.md"), "# Logic\n");
  await writeFile(join(skill, "graph.yaml"), "fake-invalid\n");
  const client = new Client({ name: "watch-invalid-test", version: "1" });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [fileURLToPath(new URL("../../dist/server.mjs", import.meta.url))], stderr: "pipe", env: fakeRuntimeEnv() }));
  t.after(() => client.close());

  const shown = await client.callTool({ name: "show_graph", arguments: { skill_root: skill } });
  assert.notEqual(shown.isError, true, JSON.stringify(shown));
  assert.equal(shown.structuredContent.graph, null);
  assert.equal(shown.structuredContent.compile.status, "failed");
  assert.match(shown.content[0].text, /currently invalid/);
  assert.match(shown.content[0].text, /\[F-fake-runtime\] graph\.yaml is marked fake-invalid \(graph\.yaml:1\)/);
  const inspected = await client.callTool({ name: "inspect_graph", arguments: { skill_root: skill } });
  assert.equal(inspected.structuredContent.compile.diagnostics[0].code, "[F-fake-runtime]");

  const first = await client.callTool({ name: "watch_graph", arguments: { skill_root: skill, timeout_ms: 5000 } });
  assert.equal(first.structuredContent.event.type, "invalid");
  assert.equal(first.structuredContent.event.diagnostics[0].code, "[F-fake-runtime]");
  const pending = client.callTool({ name: "watch_graph", arguments: { skill_root: skill, after_revision: first.structuredContent.revision, timeout_ms: 15000 } });
  await new Promise(resolve => setTimeout(resolve, 100));
  await writeFile(join(skill, "graph.yaml"), graphYaml("recovered"));
  const recovered = await pending;
  assert.equal(recovered.structuredContent.event.type, "snapshot");
  assert.equal(recovered.structuredContent.event.data.graph.id, "recovered");
});
