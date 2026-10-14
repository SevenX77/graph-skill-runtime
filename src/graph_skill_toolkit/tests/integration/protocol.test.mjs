import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, readFile, readdir, copyFile, rm, mkdir, writeFile, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { graph, matchesProbeGraph } from "../../application/graph/demo/graph.mjs";
import { graphPayload } from "../../adapters/claude/presentation/guidance/index.mjs";
import { validateCanvas } from "../../ui/canvas/index.mjs";
import { SNAPSHOT_SLOT, snapshotHtml } from "../../ui/template/publisher.mjs";
import { fakeRuntimeEnv } from "../support/runtime.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

test("MCP resource identity binds HTML and retires backend credentials across restarts", async (context) => {
  const isolated = await mkdtemp(join(tmpdir(), "graph-resource-upgrade-"));
  context.after(() => rm(isolated, { recursive: true, force: true }));
  await copyFile(join(root, "dist/server.mjs"), join(isolated, "server.mjs"));
  const original = await readFile(join(root, "dist/canvas.html"), "utf8");
  const uris = [];
  for (const [index, html] of [original, original, `${original}\n<!-- changed build -->`].entries()) {
    await writeFile(join(isolated, "canvas.html"), html);
    const client = new Client({ name: `resource-test-${index}`, version: "1" });
    const transport = new StdioClientTransport({ command: process.execPath, args: [join(isolated, "server.mjs")], stderr: "pipe", env: fakeRuntimeEnv() });
    try {
      await client.connect(transport);
      const { tools } = await client.listTools();
      const uri = tools.find(tool => tool.name === "show_graph")._meta.ui.resourceUri;
      assert.equal(tools.find(tool => tool.name === "inspect_graph")._meta.ui.resourceUri, undefined);
      const { resources } = await client.listResources();
      assert.deepEqual(resources.map(resource => resource.uri), [uri]);
      const resource = await client.readResource({ uri });
      const slot = /<script id="graph-skill-snapshot" type="application\/json">([\s\S]*?)<\/script>/;
      const { graphBackend, serverInfo } = JSON.parse(slot.exec(resource.contents[0].text)[1]);
      assert.equal(uri, `ui://graph-skill/canvas-${createHash("sha256").update(snapshotHtml(html, { graphBackend, serverInfo })).digest("hex")}.html`);
      assert.equal(resource.contents[0].text.replace(slot, SNAPSHOT_SLOT), html);
      if (index === 2) await assert.rejects(client.readResource({ uri: uris[0] }));
      uris.push(uri);
    } finally { await client.close(); }
  }
  assert.notEqual(uris[0], uris[1]);
  assert.notEqual(uris[1], uris[2]);
});

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
  const transport = new StdioClientTransport({ command: process.execPath, args: [join(isolated, "server.mjs")], cwd: tmpdir(), stderr: "pipe", env: fakeRuntimeEnv() });
  const client = new Client({ name: "graph-canvas-test", version: "0.0.1" });
  let stderr = "";
  transport.stderr.on("data", (chunk) => { stderr += chunk; });
  try {
    await client.connect(transport);
    const { tools } = await client.listTools();
    assert.deepEqual(tools.map(tool => tool.name).sort(), ["inspect_graph", "list_canvas_tools", "show_graph", "watch_graph"]);
    const inventory = await client.callTool({ name: "list_canvas_tools", arguments: {} });
    assert.equal(inventory.structuredContent.scope, "originating-server");
    assert.deepEqual(inventory.structuredContent.tools.map(item => item.name), ["inspect_graph", "watch_graph", "list_canvas_tools"]);
    const tool = tools.find(tool => tool.name === "show_graph");
    const inspect = tools.find(tool => tool.name === "inspect_graph");
    assert.equal(inspect.annotations.readOnlyHint, true);
    assert.deepEqual(inspect._meta.ui.visibility, ["app", "model"]);
    assert.equal(inspect._meta.ui.resourceUri, undefined);
    assert.equal((await client.callTool({name:"inspect_graph",arguments:{skill_root:isolated}})).isError,true);
    assert.equal(tool.name, "show_graph");
    assert.equal(tool.annotations.readOnlyHint, false);
    assert.equal(tool.annotations.destructiveHint, false);
    assert.equal(tool.annotations.openWorldHint, false);
    const template = await readFile(join(root, "dist/canvas.html"), "utf8");
    assert.match(tool._meta.ui.resourceUri, /^ui:\/\/graph-skill\/canvas-[a-f0-9]{64}\.html$/);
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
    assert.equal(actual.structuredContent.document, undefined);
    const {hostInfo,...graphContent}=actual.structuredContent;
    assert.equal(hostInfo.id,"unknown");assert.equal(hostInfo.name,"graph-canvas-test");
    assert.deepEqual((await client.callTool({name:"inspect_graph",arguments:{skill_root:actual.structuredContent.skillRoot}})).structuredContent,graphContent);
    assert.deepEqual(actual.structuredContent.graph.nodes.map(node => node.kind), ["INPUT", "LOGIC", "OUTPUT"]);
    const native = validateCanvas(graphPayload({ result: actual }));
    assert.equal(native.skillRoot, await realpath(skill));
    assert.equal(native.graph.nodes[1].label, 'process');
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
    // A closed Codex tab must retain its sidebar display mode. Advertising
    // inline makes the host downgrade that same session on close and reuse it
    // inline on the next show_graph. Check both discovery and returned bytes.
    const codexDisplay = { availableDisplayModes: ["fullscreen"], preferredDisplayMode: "fullscreen" };
    assert.deepEqual(resources[0]._meta["openai/ui"], codexDisplay);
    const { contents } = await client.readResource({ uri: tool._meta.ui.resourceUri });
    assert.deepEqual(contents[0]._meta["openai/ui"], codexDisplay);
    assert.equal(contents[0].mimeType, RESOURCE_MIME_TYPE);
    const slot=/<script id="graph-skill-snapshot" type="application\/json">([\s\S]*?)<\/script>/;
    const startup = JSON.parse(slot.exec(contents[0].text)[1]);
    assert.deepEqual(startup.hostInfo,hostInfo);
    assert.equal(tool._meta.ui.resourceUri, `ui://graph-skill/canvas-${createHash("sha256").update(snapshotHtml(template, {graphBackend:startup.graphBackend,serverInfo:startup.serverInfo})).digest("hex")}.html`);
    assert.equal(contents[0].text.replace(slot,SNAPSHOT_SLOT), await readFile(join(root, "dist/canvas.html"), "utf8"));
    assert.deepEqual(contents[0]._meta.ui.csp, { connectDomains: [startup.graphBackend.url], resourceDomains: [] });
    assert.doesNotMatch(contents[0].text, /<script[^>]+src=|<link[^>]+href=/i);
    assert.match(contents[0].text, /id="app"/);
    assert.match(contents[0].text, /skill-path/);
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
