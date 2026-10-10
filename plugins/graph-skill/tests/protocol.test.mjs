import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, readFile, readdir, copyFile, rm, mkdir, writeFile, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { graph, matchesProbeGraph } from "../src/graph.mjs";
import { graphPayload, makeCanvas } from "../claude-mod/hooks/register.js";

const root = fileURLToPath(new URL("../", import.meta.url));

test("host JSON key reordering preserves the fixture while invalid graph data is rejected", () => {
  const reordered = JSON.parse(JSON.stringify(graph), (_key, value) => {
    if (value && typeof value === "object" && !Array.isArray(value)) return Object.fromEntries(Object.entries(value).reverse());
    return value;
  });
  assert.equal(matchesProbeGraph(reordered), true);
  assert.equal(matchesProbeGraph({ ...reordered, nodes: reordered.nodes.slice(1) }), false);
  assert.equal(matchesProbeGraph({ ...reordered, edges: [{ from: "input", to: "output" }] }), false);
  assert.equal(matchesProbeGraph(null), false);
});

test("bundled plugin serves the read-only graph and self-contained UI from an unrelated cwd", async (context) => {
  const isolated = await mkdtemp(join(tmpdir(), "graph canvas 中文 "));
  context.after(() => rm(isolated, { recursive: true, force: true }));
  for (const file of ["server.mjs", "canvas.html"]) await copyFile(join(root, "dist", file), join(isolated, file));
  const before = await readdir(isolated);
  const transport = new StdioClientTransport({ command: process.execPath, args: [join(isolated, "server.mjs")], cwd: tmpdir(), stderr: "pipe" });
  const client = new Client({ name: "graph-canvas-test", version: "0.0.1" });
  let stderr = "";
  transport.stderr.on("data", (chunk) => { stderr += chunk; });
  try {
    await client.connect(transport);
    const { tools } = await client.listTools();
    assert.equal(tools.length, 1);
    const tool = tools[0];
    assert.equal(tool.name, "show_graph");
    assert.equal(tool.annotations.readOnlyHint, true);
    assert.equal(tool.annotations.destructiveHint, false);
    assert.equal(tool.annotations.openWorldHint, false);
    assert.equal(tool._meta.ui.resourceUri, "ui://graph-skill/canvas-v2.html");
    const result = await client.callTool({ name: tool.name, arguments: {} });
    assert.notEqual(result.isError, true);
    assert.deepEqual(result.structuredContent.graph.nodes.map((node) => node.id), ["input", "process", "output"]);
    assert.equal(result.structuredContent.graph.edges.length, 2);
    assert.equal(result.structuredContent.skillRoot, null);
    const skill = join(isolated, "业务 Skill");
    await mkdir(join(skill, "phases", "process"), { recursive: true });
    await writeFile(join(skill, "SKILL.md"), "---\nname: test\n---\n");
    await writeFile(join(skill, "graph.yaml"), "schema_version: gskill.graph.v1\ngraph_id: actual\nphases:\n  - id: process\n    depends_on: [input]\n    output: true\n");
    await writeFile(join(skill, "phases", "process", "LOGIC.md"), "# Logic\n");
    const actual = await client.callTool({ name: tool.name, arguments: { skill_root: skill } });
    assert.notEqual(actual.isError, true);
    assert.equal(actual.structuredContent.skillRoot, await realpath(skill));
    assert.equal(actual.structuredContent.graph.id, "actual");
    assert.deepEqual(actual.structuredContent.graph.nodes.map(node => node.kind), ["INPUT", "LOGIC", "OUTPUT"]);
    const native = makeCanvas(graphPayload({ result: actual }));
    assert.equal(native.root, await realpath(skill));
    assert.match(native.source, />process</);
    assert.equal(native.graph.edges.length, 2);
    for (const skill_root of ["relative", join(isolated, "missing"), isolated]) {
      assert.equal((await client.callTool({ name: tool.name, arguments: { skill_root } })).isError, true);
    }
    await rm(skill, { recursive: true });
    const rejected = await client.callTool({ name: tool.name, arguments: { skill_path: "anything" } });
    assert.equal(rejected.isError, true);
    const { resources } = await client.listResources();
    assert.equal(resources.length, 1);
    assert.equal(resources[0].uri, tool._meta.ui.resourceUri);
    const { contents } = await client.readResource({ uri: tool._meta.ui.resourceUri });
    assert.equal(contents[0].mimeType, RESOURCE_MIME_TYPE);
    assert.equal(contents[0].text, await readFile(join(root, "dist/canvas.html"), "utf8"));
    assert.deepEqual(contents[0]._meta.ui.csp, { connectDomains: [], resourceDomains: [] });
    assert.doesNotMatch(contents[0].text, /<(?:input|textarea|select)\b|<script[^>]+src=|<link[^>]+href=/i);
    assert.match(contents[0].text, /id="skill-path"/);
    assert.doesNotMatch(contents[0].text, /APP_BUNDLE/);
    await assert.rejects(client.readResource({ uri: "file:///not-exposed" }));
  } finally {
    await client.close();
  }
  assert.equal(stderr, "");
  assert.deepEqual(await readdir(isolated), before);
});

test("both host manifests resolve to the same bundled implementation", async () => {
  const json = async (path) => JSON.parse(await readFile(join(root, path), "utf8"));
  const portable = await json("plugin.json");
  const claude = await json(".claude-plugin/plugin.json");
  for (const field of ["name", "version", "description", "author"]) assert.deepEqual(portable[field], claude[field]);
  const codexMcp = (await json("mcp.json")).mcpServers["graph-skill-canvas"];
  const claudeMcp = (await json(".mcp.json")).mcpServers["graph-skill-canvas"];
  assert.deepEqual({ ...codexMcp, args: codexMcp.args.map((value) => value.replace("${PLUGIN_ROOT}", root)) },
    { ...claudeMcp, args: claudeMcp.args.map((value) => value.replace("${CLAUDE_PLUGIN_ROOT}", root)) });
  assert.equal(portable.extensions?.["com.openai"]?.hooks, undefined);
  assert.equal(claude.hooks, undefined);
  const hook = (await json("hooks/hooks.json")).hooks.PostToolUse[0];
  assert.equal(hook.hooks[0].type, "command");
  assert.match(hook.hooks[0].command, /dist\/after-tool\.mjs/);
});
