import assert from "node:assert/strict";
import test from "node:test";
import { mkdir, mkdtemp, rm, writeFile, appendFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { createLocalHttpServer } from "../../plugin_base/backend/http/index.mjs";
import { createPageHost, pageHostInfo, transcriptEvents, transcriptPath } from "../../plugin_base/adapters/claude_page/server/index.mjs";
import { claudePageDriver, pageConnection } from "../../plugin_base/adapters/claude_page/page/index.mjs";
import { hostAdapter } from "../../plugin_base/adapters/facade/index.mjs";
import { identifyHost } from "../../plugin_base/adapters/detection/index.mjs";

const client = { name: "claude-code", version: "2.1.309" };

async function setup(t, env = { CLAUDE_CODE_SESSION_ID: "s1" }) {
  const home = await mkdtemp(join(tmpdir(), "page host "));
  const http = createLocalHttpServer();
  t.after(async () => { await http.close(); await rm(home, { recursive: true, force: true }); });
  const host = createPageHost({ http, serverName: "graph-skill-canvas", env, home });
  await http.open();
  const page = host.createView({ key: "k", hostInfo: pageHostInfo(client), projectRoot: join(home, "project"),
    tools: [{ name: "lab_echo", description: "echo", call: async args => ({ echo: args }) }] });
  const connection = pageConnection({ snapshot: () => ({ pageHost: page }), pageOrigin: http.origin });
  await connection.connect({ receive() {}, fail(error) { throw error; } });
  t.after(() => connection.dispose());
  return { home, host, page, http, connection };
}

test("only the Claude MCP client opens the browser-page route", () => {
  assert.equal(pageHostInfo(client).transport, "http-page");
  assert.throws(() => pageHostInfo({ name: "codex-mcp-client", version: "1" }));
});

test("the page confirms Claude from the plugin process with no Mod", async t => {
  const { connection } = await setup(t);
  const info = identifyHost(await connection.inspect());
  assert.deepEqual([info.id, info.status, info.transport, info.identitySource, info.sessionId], ["claude", "confirmed", "http-page", "mcp-client", "s1"]);
  assert.equal(info.capabilities["views.open"].state, "unavailable");
  assert.equal(info.capabilities["files.openFile"].state, "unavailable");
  assert.equal(info.capabilities["tools.call"].scope, "originating-server");
});

test("a page with no session id reports events as unavailable", async t => {
  const { connection } = await setup(t, {});
  assert.equal(identifyHost(await connection.inspect()).capabilities["events.subscribe"].state, "unavailable");
});

test("a wrong credential and another origin are refused", async t => {
  const { http, page } = await setup(t);
  assert.equal((await fetch(http.origin + "/page/capabilities", { headers: { Authorization: "Bearer wrong" } })).status, 401);
  assert.equal((await fetch(http.origin + "/page/capabilities", { headers: { Authorization: "Bearer " + page.token, Origin: "http://evil.test" } })).status, 403);
});

test("tools run in the plugin process and foreign tools are unsupported", async t => {
  const { connection } = await setup(t);
  const driver = claudePageDriver(connection, { document: {}, window: {} });
  const call = await driver.invoke("tools.call", { tool: { name: "lab_echo", server: "graph-skill-canvas", scope: "session" }, arguments: { text: "x" } });
  assert.deepEqual([call.status, call.data.echo.text], ["completed", "x"]);
  assert.equal((await driver.invoke("tools.call", { tool: { name: "Read" }, arguments: {} })).status, "unsupported");
  assert.equal((await driver.invoke("tools.call", { tool: { name: "lab_echo", server: "other" }, arguments: {} })).status, "unsupported");
  assert.deepEqual((await driver.invoke("tools.list", {})).data.tools.map(tool => tool.name), ["lab_echo"]);
});

test("context is stored for the model to pull, and skills are an incomplete scan", async t => {
  const { connection, host, home } = await setup(t);
  const driver = claudePageDriver(connection, { document: {}, window: {} });
  assert.equal(host.context("k"), null);
  assert.equal((await driver.invoke("context.update", { snapshot: { selection: "a" } })).status, "accepted");
  assert.match(host.context("k"), /^Plugin page context .*"selection":"a"/);
  await mkdir(join(home, ".claude", "skills", "demo"), { recursive: true });
  await writeFile(join(home, ".claude", "skills", "demo", "SKILL.md"), "x");
  await mkdir(join(home, ".claude", "skills", "not-a-skill"), { recursive: true });
  const listed = await driver.invoke("skills.list", {});
  assert.deepEqual([listed.data.complete, listed.data.skills], [false, ["demo"]]);
});

test("transcript lines become events from the page's start, and a partial line waits", async t => {
  const { connection, home } = await setup(t);
  const path = transcriptPath(home, join(home, "project"), "s1");
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, JSON.stringify({ type: "assistant", message: { stop_reason: "end_turn", content: [] } }) + "\n");
  const start = await connection.request("/page/events?after=-1");
  assert.deepEqual(start.events, []);
  const use = JSON.stringify({ type: "assistant", timestamp: "t1", message: { stop_reason: "tool_use", content: [{ type: "tool_use", id: "u1", name: "Read" }] } });
  const output = JSON.stringify({ type: "user", timestamp: "t2", message: { content: [{ type: "tool_result", tool_use_id: "u1", is_error: true }] } });
  await appendFile(path, use + "\n" + output + "\n" + '{"partial"');
  const next = await connection.request("/page/events?after=" + start.cursor);
  assert.deepEqual(next.events, [{ type: "tool.completed", at: "t2", data: { tool: "Read", isError: true } }]);
  assert.deepEqual((await connection.request("/page/events?after=" + next.cursor)).events, []);
  assert.deepEqual(transcriptEvents("not json\n", new Map()), []);
});

test("the display mode follows the page's real state", async () => {
  const hanging = { fullscreenElement: null, documentElement: { requestFullscreen: () => new Promise(() => {}) } };
  const stuck = await claudePageDriver({}, { document: hanging, window: {}, fullscreenWaitMs: 5 }).invoke("views.requestDisplayMode", { mode: "fullscreen" });
  assert.deepEqual([stuck.status, stuck.data.mode, stuck.evidence.observed.fullscreen], ["rejected", "inline", false]);
  const working = { fullscreenElement: null, documentElement: { requestFullscreen: async () => { working.fullscreenElement = {}; } }, exitFullscreen: async () => { working.fullscreenElement = null; } };
  const driver = claudePageDriver({}, { document: working, window: {}, fullscreenWaitMs: 5 });
  assert.equal((await driver.invoke("views.requestDisplayMode", { mode: "fullscreen" })).status, "completed");
  assert.equal((await driver.invoke("views.requestDisplayMode", { mode: "inline" })).status, "completed");
  assert.equal(working.fullscreenElement, null);
  assert.equal((await driver.invoke("views.requestDisplayMode", { mode: "pip" })).status, "unsupported");
  const refused = { fullscreenElement: null, documentElement: { requestFullscreen: async () => { throw new Error("denied"); } } };
  assert.match((await claudePageDriver({}, { document: refused, window: {} }).invoke("views.requestDisplayMode", { mode: "fullscreen" })).message, /denied/);
});

test("the facade answers an unconnected interface without dispatching it", async t => {
  const { connection } = await setup(t);
  const sent = [];
  const adapter = hostAdapter(() => connection, () => ({ invoke: async (...args) => { sent.push(args); return { status: "completed", message: "" }; } }));
  await adapter.connect({ receive() {}, fail() {} });
  const result = await adapter.invoke("files.openFile", { path: "C:/a.txt" });
  assert.deepEqual([result.status, result.data.capabilityState, sent.length], ["unsupported", "unavailable", 0]);
});
