import assert from "node:assert/strict";
import test from "node:test";
import { link, lstat, mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { join, resolve, sep } from "node:path";
import { tmpdir } from "node:os";
import { createPreviewConfiguration } from "../adapters/claude/preview_configuration/index.mjs";

async function fixture(t) {
  const prefix = join(await realpath(tmpdir()), "gskill-preview-config-");
  const root = await realpath(await mkdtemp(prefix));
  t.after(async () => {
    assert.ok(resolve(root).startsWith(prefix), "fixture cleanup remains within its allocated prefix");
    await rm(root, { recursive: true, force: true });
  });
  return { root, folder: join(root, ".claude"), path: join(root, ".claude", "launch.json") };
}
const exists = path => lstat(path).then(() => true, error => { if (error.code === "ENOENT") return false; throw error; });
const read = async path => JSON.parse(await readFile(path, "utf8"));

test("URL-only entry is lazy, stable for an origin, updated by its owner, and removed on close", async t => {
  const { root, folder, path } = await fixture(t);
  const problems = [], owner = createPreviewConfiguration({ report: message => problems.push(message) });
  assert.equal(await exists(folder), false);
  const first = await owner.ensure(root, "http://127.0.0.1:43210/");
  assert.deepEqual(first, { name: first.name, projectRoot: root });
  assert.match(first.name, /^graph-skill-[a-f0-9-]+$/);
  const expected = { version: "0.0.1", configurations: [{ name: first.name, url: "http://127.0.0.1:43210", port: 43210 }] };
  assert.deepEqual(await read(path), expected);
  const before = await readFile(path);
  assert.deepEqual(await owner.ensure(root, "http://127.0.0.1:43210"), first);
  assert.deepEqual(await readFile(path), before);
  assert.deepEqual(await owner.ensure(root, "http://127.0.0.1:43211"), first);
  assert.deepEqual((await read(path)).configurations, [{ name: first.name, url: "http://127.0.0.1:43211", port: 43211 }]);
  await owner.close(); await owner.close();
  assert.equal(await exists(path), false);
  assert.equal(await exists(folder), false);
  assert.deepEqual(problems, []);
  await assert.rejects(owner.ensure(root, "http://127.0.0.1:43210"), /closed/);
});

test("existing JSON fields and unrelated configurations survive ensure and cleanup", async t => {
  const { root, folder, path } = await fixture(t);
  await mkdir(folder);
  const original = { version: "0.0.1", custom: { enabled: true }, configurations: [{ name: "user-app", runtimeExecutable: "npm", runtimeArgs: ["run", "dev"], port: 5173 }] };
  await writeFile(path, JSON.stringify(original));
  const owner = createPreviewConfiguration();
  const entry = await owner.ensure(root, "http://127.0.0.1:40001");
  const installed = await read(path);
  assert.deepEqual(installed.custom, original.custom);
  assert.deepEqual(installed.configurations[0], original.configurations[0]);
  assert.equal(installed.configurations[1].name, entry.name);
  await owner.close();
  assert.deepEqual(await read(path), original);
  assert.equal(await exists(folder), true);
});

test("two cooperating owners preserve each other's entries, including a port update", async t => {
  const { root, path } = await fixture(t);
  const first = createPreviewConfiguration(), second = createPreviewConfiguration();
  const results = await Promise.allSettled([first.ensure(root, "http://127.0.0.1:40001"), second.ensure(root, "http://127.0.0.1:40002")]);
  assert.ok(results.some(result => result.status === "fulfilled"));
  for (let index = 0; index < results.length; index++) {
    if (results[index].status === "rejected") {
      assert.match(results[index].reason.message, /busy/);
      await [first, second][index].ensure(root, `http://127.0.0.1:${40001 + index}`);
    }
  }
  assert.equal((await read(path)).configurations.length, 2);
  await first.ensure(root, "http://127.0.0.1:40003");
  await first.close();
  assert.deepEqual((await read(path)).configurations.map(item => item.port), [40002]);
  await second.close();
  // Whichever contender created the document may remove its exact after-image;
  // otherwise cleanup leaves an empty shared document.
  if (await exists(path)) assert.deepEqual((await read(path)).configurations, []);
});

test("a modified owned entry is preserved byte-for-byte and blocks update", async t => {
  const { root, path } = await fixture(t);
  const reports = [], owner = createPreviewConfiguration({ report: text => reports.push(text) });
  await owner.ensure(root, "http://127.0.0.1:40001");
  const document = await read(path);
  document.configurations[0].url = "http://127.0.0.1:49999";
  const changed = JSON.stringify(document, null, 4);
  await writeFile(path, changed);
  await assert.rejects(owner.ensure(root, "http://127.0.0.1:40002"), /modified/);
  await owner.close();
  assert.equal(await readFile(path, "utf8"), changed);
  assert.ok(reports.some(message => /preserved/.test(message)));
});

test("unrelated user changes prevent deletion of a newly created file even after an owner update", async t => {
  const { root, path } = await fixture(t);
  const owner = createPreviewConfiguration();
  await owner.ensure(root, "http://127.0.0.1:40001");
  const document = await read(path);
  document.userSetting = "keep";
  await writeFile(path, JSON.stringify(document));
  await owner.ensure(root, "http://127.0.0.1:40002");
  await owner.close();
  assert.deepEqual(await read(path), { version: "0.0.1", configurations: [], userSetting: "keep" });
});

test("busy locks fail immediately without stealing or deleting another owner's lock", async t => {
  const { root, folder, path } = await fixture(t);
  await mkdir(folder);
  const lock = join(folder, ".graph-skill-preview.lock");
  await writeFile(lock, "another-owner");
  const owner = createPreviewConfiguration();
  await assert.rejects(owner.ensure(root, "http://127.0.0.1:40001"), /busy.*Wait for its owning operation/);
  await owner.close();
  assert.equal(await readFile(lock, "utf8"), "another-owner");
  assert.equal(await exists(path), false);
});

test("malformed existing configurations are rejected without rewriting their bytes", async t => {
  const { root, folder, path } = await fixture(t);
  await mkdir(folder);
  for (const value of ["not-json", "[]", '{"configurations":{}}']) {
    await writeFile(path, value);
    const owner = createPreviewConfiguration();
    await assert.rejects(owner.ensure(root, "http://127.0.0.1:40001"), /preserved/);
    await owner.close();
    assert.equal(await readFile(path, "utf8"), value);
  }
});

test("invalid origins and noncanonical roots cause no configuration writes", async t => {
  const { root, folder } = await fixture(t);
  const owner = createPreviewConfiguration();
  for (const origin of ["http://localhost:1234", "http://127.0.0.1:01234", "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://127.0.0.1:1234/view", "http://127.0.0.1:1234?x", "http://127.0.0.1:1234#x", "https://127.0.0.1:1234", "http://user@127.0.0.1:1234"]) {
    await assert.rejects(owner.ensure(root, origin));
  }
  await assert.rejects(owner.ensure("relative", "http://127.0.0.1:1234"), /absolute/);
  await assert.rejects(owner.ensure(root + sep + ".", "http://127.0.0.1:1234"), /canonical/);
  await owner.close();
  assert.equal(await exists(folder), false);
});

test("redirected directories and hard-linked or nonregular launch files are rejected", async t => {
  const { root, folder, path } = await fixture(t);
  const target = join(root, "elsewhere"); await mkdir(target);
  await symlink(target, folder, process.platform === "win32" ? "junction" : "dir");
  const owner = createPreviewConfiguration();
  await assert.rejects(owner.ensure(root, "http://127.0.0.1:1234"), /canonical/);
  await rm(folder); await mkdir(folder);
  const original = join(root, "user-file.json");
  await writeFile(original, '{"configurations":[]}'); await link(original, path);
  await assert.rejects(owner.ensure(root, "http://127.0.0.1:1234"), /single-link/);
  assert.equal(await readFile(original, "utf8"), '{"configurations":[]}');
  await rm(path); await mkdir(path);
  await assert.rejects(owner.ensure(root, "http://127.0.0.1:1234"), /single-link/);
  await owner.close();
});
