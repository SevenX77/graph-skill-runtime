import assert from "node:assert/strict";
import test from "node:test";
import { EventEmitter } from "node:events";
import { mkdtemp, mkdir, readFile, realpath, rm, symlink, writeFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createLocalCapabilities, systemCommand } from "../../plugin_base/local/node/index.mjs";
import { createLocalClient, httpLocalTransport } from "../../plugin_base/local/page/index.mjs";
import { createLocalHttpServer } from "../../plugin_base/backend/http/index.mjs";

async function sandbox(t) {
  const root = await mkdtemp(join(tmpdir(), "local capability 中文 "));
  t.after(() => rm(root, { recursive: true, force: true }));
  const allowed = join(root, "allowed");
  await mkdir(allowed);
  await writeFile(join(allowed, "a.txt"), "第一行\n");
  await writeFile(join(root, "secret.txt"), "outside");
  return { root, allowed };
}

test("read and write stay inside granted roots and report their evidence", async t => {
  const { root, allowed } = await sandbox(t);
  const connection = createLocalCapabilities().createConnection();
  t.after(() => connection.close());
  assert.equal((await connection.call("local.files.read", { path: join(allowed, "a.txt") })).status, "rejected");
  await connection.allow(allowed);
  const read = await connection.call("local.files.read", { path: join(allowed, "a.txt") });
  assert.deepEqual([read.status, read.data.content, read.evidence.observed.size], ["completed", "第一行\n", Buffer.byteLength("第一行\n")]);
  assert.equal((await connection.call("local.files.read", { path: join(root, "secret.txt") })).status, "rejected");
  assert.equal((await connection.call("local.files.read", { path: join(allowed, "..", "secret.txt") })).status, "rejected");
  assert.equal((await connection.call("local.files.read", { path: join(allowed, "a.txt"), maxBytes: 2 })).status, "rejected");
  const written = await connection.call("local.files.write", { path: join(allowed, "new.txt"), content: "新内容 ✓" });
  assert.equal(written.status, "completed");
  assert.equal(written.data.created, true);
  assert.equal(written.evidence.observed.matchesSent, true);
  assert.equal(written.evidence.receipt.replacedBy, "rename");
  assert.equal(await readFile(join(allowed, "new.txt"), "utf8"), "新内容 ✓");
  const binary = await connection.call("local.files.write", { path: join(allowed, "new.txt"), content: Buffer.from([0, 255]).toString("base64"), encoding: "base64" });
  assert.deepEqual([binary.data.created, [...await readFile(join(allowed, "new.txt"))]], [false, [0, 255]]);
  assert.equal((await connection.call("local.files.read", { path: join(allowed, "new.txt") })).status, "rejected");
  assert.equal((await connection.call("local.files.read", { path: join(allowed, "new.txt"), encoding: "base64" })).data.content, "AP8=");
  assert.equal((await connection.call("local.files.write", { path: join(root, "escape.txt"), content: "x" })).status, "rejected");
  assert.equal((await connection.call("local.files.read", { path: "relative.txt" })).status, "error");
});

test("watch reports created, modified and deleted until it is stopped", async t => {
  const { allowed } = await sandbox(t);
  const connection = createLocalCapabilities({ pollMs: 20 }).createConnection();
  t.after(() => connection.close());
  await connection.allow(allowed);
  const target = join(allowed, "watched.txt");
  const started = await connection.call("local.files.watch", { paths: [target] });
  assert.equal(started.status, "completed");
  assert.deepEqual(started.data.initial.map(item => item.exists), [false]);
  const changes = [];
  let cursor = 0;
  async function next() {
    const answer = await connection.wait(cursor, 2000);
    cursor = answer.cursor;
    changes.push(...answer.events.map(event => event.data.change));
  }
  await writeFile(target, "1"); await next();
  await new Promise(done => setTimeout(done, 40));
  await writeFile(target, "22"); await next();
  await unlink(target); await next();
  assert.deepEqual(changes, ["created", "modified", "deleted"]);
  assert.equal((await connection.call("local.files.unwatch", { watchId: started.data.watchId })).status, "completed");
  await writeFile(target, "3");
  assert.deepEqual((await connection.wait(cursor, 100)).events, []);
});

test("system actions are shell-free platform commands with honest evidence", async () => {
  const win = systemCommand("reveal", "C:/Users/a b/file.txt", { platform: "win32", env: { SystemRoot: "C:\\Windows" } });
  assert.deepEqual(win, { command: "C:\\Windows\\explorer.exe", args: ['/select,"C:\\Users\\a b\\file.txt"'], options: { windowsVerbatimArguments: true } });
  assert.deepEqual(systemCommand("open", "https://example.com/?a=1&b=2", { platform: "win32", env: { SystemRoot: "C:\\Windows" } }).args, ["url.dll,FileProtocolHandler", "https://example.com/?a=1&b=2"]);
  assert.deepEqual(systemCommand("reveal", "/tmp/x/file.txt", { platform: "darwin" }), { command: "/usr/bin/open", args: ["-R", "/tmp/x/file.txt"], options: {} });
  assert.deepEqual(systemCommand("reveal", "/tmp/x/file.txt", { platform: "linux" }).args, ["/tmp/x"]);
  assert.deepEqual(systemCommand("reveal", "/tmp/x", { platform: "linux", isDirectory: true }).args, ["/tmp/x"]);

  const spawned = [];
  const spawnProcess = (command, args, options) => {
    const child = new EventEmitter();
    child.pid = 42;
    spawned.push({ command, args, options });
    setImmediate(() => { child.emit("spawn"); child.emit("exit", 1); });
    return child;
  };
  const connection = createLocalCapabilities({ platform: "win32", env: { SystemRoot: "C:\\Windows" }, spawnProcess }).createConnection();
  const opened = await connection.call("local.system.openExternal", { url: "https://example.com/" });
  assert.equal(opened.status, "accepted");
  assert.deepEqual(opened.evidence.receipt, { pid: 42, exitCode: 1 });
  assert.equal(spawned[0].options.shell, false);
  assert.match(opened.evidence.limits[0], /不报告窗口是否真的出现/);
  assert.equal((await connection.call("local.system.openExternal", { url: "file:///etc/passwd" })).status, "error");
  assert.equal((await connection.call("local.system.revealInFileManager", { path: "C:/not/granted" })).status, "rejected");
  const failing = createLocalCapabilities({ spawnProcess: () => { const child = new EventEmitter(); setImmediate(() => child.emit("error", new Error("ENOENT xdg-open"))); return child; } }).createConnection();
  const failed = await failing.call("local.system.openExternal", { url: "https://example.com/" });
  assert.deepEqual([failed.status, failed.evidence.observed.launched], ["error", false]);
});

test("a packaged-host file redirect stays inside its nominal root, a link out of the root does not", async t => {
  const { root, allowed } = await sandbox(t);
  const storage = join(root, "package-storage");
  await mkdir(storage);
  await writeFile(join(storage, "a.txt"), "第一行\n");
  // A packaged host resolves the file into its own storage; its directory resolves nominally.
  const realpathOf = async path => path === join(allowed, "a.txt") ? join(storage, "a.txt") : realpath(path);
  const connection = createLocalCapabilities({ realpathOf }).createConnection();
  await connection.allow(allowed);
  const read = await connection.call("local.files.read", { path: join(allowed, "a.txt") });
  assert.deepEqual([read.status, read.data.content], ["completed", "第一行\n"]);
  const write = await connection.call("local.files.write", { path: join(allowed, "a.txt"), content: "新\n" });
  assert.equal(write.status, "completed");
  const outside = join(root, "outside-dir");
  await mkdir(outside);
  await writeFile(join(outside, "b.txt"), "secret");
  await symlink(outside, join(allowed, "link"), process.platform === "win32" ? "junction" : "dir");
  assert.equal((await connection.call("local.files.read", { path: join(allowed, "link", "b.txt") })).status, "rejected");
  assert.equal((await connection.call("local.files.read", { path: join(root, "secret.txt") })).status, "rejected");
});

test("reveal hands the file manager the real path behind a redirected one", async t => {
  const { root, allowed } = await sandbox(t);
  const alias = join(root, "alias");
  await symlink(allowed, alias, process.platform === "win32" ? "junction" : "dir");
  const spawned = [];
  const spawnProcess = (command, args) => {
    const child = new EventEmitter();
    spawned.push(args);
    setImmediate(() => { child.emit("spawn"); child.emit("exit", 0); });
    return child;
  };
  const connection = createLocalCapabilities({ platform: "darwin", spawnProcess }).createConnection();
  await connection.allow(allowed);
  const revealed = await connection.call("local.system.revealInFileManager", { path: join(alias, "a.txt") });
  const real = await realpath(join(allowed, "a.txt"));
  assert.equal(revealed.status, "accepted");
  assert.equal(revealed.evidence.sent.realPath, real);
  assert.deepEqual(spawned[0], ["-R", real]);
});

test("the page client reaches the HTTP route with its credential and delivers watch events", async t => {
  const { allowed } = await sandbox(t);
  const http = createLocalHttpServer();
  const local = createLocalCapabilities({ http, pollMs: 20 });
  await http.open();
  t.after(async () => { local.close(); await http.close(); });
  const connection = local.createConnection();
  await connection.allow(allowed);
  assert.equal((await fetch(http.origin + "/local/call", { method: "POST", body: "{}" })).status, 401);
  const client = createLocalClient(httpLocalTransport(connection.descriptor));
  const read = await client.files.read({ path: join(allowed, "a.txt") });
  assert.deepEqual([read.status, read.data.content, read.evidence.sent], ["completed", "第一行\n", { path: join(allowed, "a.txt") }]);
  const events = [];
  const watched = await client.files.watch({ paths: [join(allowed, "a.txt")] }, event => events.push(event));
  assert.equal(watched.status, "completed");
  await client.files.write({ path: join(allowed, "a.txt"), content: "changed" });
  for (let i = 0; i < 100 && !events.length; i++) await new Promise(done => setTimeout(done, 20));
  assert.deepEqual(events.map(event => [event.type, event.data.change]), [["local.files.changed", "modified"]]);
  assert.equal((await watched.stop()).status, "completed");
  client.dispose();
  const none = createLocalClient(null);
  assert.equal((await none.files.read({ path: join(allowed, "a.txt") })).status, "unsupported");
  assert.equal((await none.system.openExternal({ url: "ftp://x" })).status, "error");
});
