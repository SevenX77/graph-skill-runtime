import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { crc32 } from "node:zlib";
import { createHash } from "node:crypto";
import test from "node:test";
import { extractArchive, memberPath } from "../src/install/archive.mjs";
import { checksumFor, compareVersions, downloadProgress, installRelease, platformTarget, releaseAssets } from "../src/install/download.mjs";

function zipFile(name, data, mode = 0o100644) {
  const filename = Buffer.from(name), content = Buffer.from(data), hash = crc32(content);
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50); local.writeUInt16LE(20, 4);
  local.writeUInt32LE(hash, 14); local.writeUInt32LE(content.length, 18);
  local.writeUInt32LE(content.length, 22); local.writeUInt16LE(filename.length, 26);
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50); central.writeUInt16LE(0x314, 4); central.writeUInt16LE(20, 6);
  central.writeUInt32LE(hash, 16); central.writeUInt32LE(content.length, 20);
  central.writeUInt32LE(content.length, 24); central.writeUInt16LE(filename.length, 28);
  central.writeUInt32LE((mode << 16) >>> 0, 38);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50); end.writeUInt16LE(1, 8); end.writeUInt16LE(1, 10);
  end.writeUInt32LE(central.length + filename.length, 12);
  end.writeUInt32LE(local.length + filename.length + content.length, 16);
  return Buffer.concat([local, filename, content, central, filename, end]);
}

test("platform selection excludes Intel Mac; releases require exact asset identities", () => {
  assert.equal(platformTarget("darwin", "arm64"), "darwin-arm64");
  assert.throws(() => platformTarget("darwin", "x64"), /No prebuilt/);
  assert.ok(compareVersions("0.10.0", "0.3.0") > 0);
  const tag = "graph-skill-toolkit-v0.3.0";
  const make = name => ({ name, size: 10, browser_download_url: `https://github.com/SevenX77/graph-skill-runtime/releases/download/${tag}/${name}` });
  const release = { tag_name: tag, assets: [make("graph-skill-0.3.0-win32-x64.zip"), make("SHA256SUMS.txt")] };
  assert.equal(releaseAssets(release, "0.3.0", "win32-x64").archive.size, 10);
  release.assets[0].browser_download_url = "https://example.com/wrong.zip";
  assert.throws(() => releaseAssets(release, "0.3.0", "win32-x64"), /invalid release asset/);
});

test("checksum selection fails closed on absent or ambiguous entries", () => {
  const line = "a".repeat(64) + "  bundle.zip\n";
  assert.equal(checksumFor(line, "bundle.zip"), "a".repeat(64));
  assert.throws(() => checksumFor(line, "other.zip"));
  assert.throws(() => checksumFor(line + line, "bundle.zip"));
});

test("ZIP extraction preserves contents and refuses traversal and symlinks", async () => {
  const directory = await mkdtemp(join(tmpdir(), "graph-skill-zip-test-"));
  try {
    const archive = join(directory, "fixture.zip");
    await writeFile(archive, zipFile("bundle/bin/hello", "fixture"));
    await extractArchive(archive, directory, "bundle");
    assert.equal(await readFile(join(directory, "bundle/bin/hello"), "utf8"), "fixture");
    assert.throws(() => memberPath("bundle/../escaped", "bundle", directory));
    await writeFile(archive, zipFile("bundle/link", "../outside", 0o120777));
    await assert.rejects(extractArchive(archive, directory, "bundle"), /link or special/);
    await assert.rejects(access(join(directory, "bundle/link")));
    await writeFile(archive, zipFile("bundle/../escaped", "bad"));
    await assert.rejects(extractArchive(archive, directory, "bundle"));
    await assert.rejects(access(join(directory, "escaped")));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("online installer verifies download before dispatch and cleans staging", async t => {
  const version = "0.3.0", target = platformTarget(), tag = `graph-skill-toolkit-v${version}`;
  const prefix = `graph-skill-${version}-${target}`, archiveName = prefix + ".zip";
  const archive = zipFile(prefix + "/bundle.json", JSON.stringify({ version, target, schema: "graph-skill.toolkit-bundle.v2" }));
  const checksum = createHash("sha256").update(archive).digest("hex");
  let incorrect = false, invoked = 0, payload;
  t.mock.method(globalThis, "fetch", async url => {
    const sums = `${incorrect ? "0".repeat(64) : checksum}  ${archiveName}\n`;
    const asset = (name, size) => ({ name, size, browser_download_url: `https://github.com/SevenX77/graph-skill-runtime/releases/download/${tag}/${name}` });
    const release = { tag_name: tag, assets: [asset(archiveName, archive.length), asset("SHA256SUMS.txt", Buffer.byteLength(sums))] };
    const content = url.endsWith(archiveName) ? archive : url.endsWith("SHA256SUMS.txt") ? sums : JSON.stringify(release);
    const response = new Response(content);
    Object.defineProperty(response, "url", { value: url });
    return response;
  });
  const messages = [];
  const options = { version, latest: false, args: ["--targets", "codex", "--dry-run"], write: message => messages.push(message), run: (node, args) => {
    invoked++; payload = args[2];
    assert.deepEqual(args.slice(3), options.args);
    assert.ok(node.startsWith(payload));
  } };
  await installRelease(options);
  assert.equal(invoked, 1);
  assert.ok(messages.some(message => message.includes("100%")));
  assert.ok(messages.findIndex(message => message.includes("SHA-256 verification complete")) <
    messages.findIndex(message => message.includes("Starting local installation")));
  await assert.rejects(access(payload));
  incorrect = true;
  await assert.rejects(installRelease(options), /checksum or size mismatch/);
  assert.equal(invoked, 1);
});

test("download progress is bounded and includes exact final size", () => {
  const messages = [], report = downloadProgress(message => messages.push(message));
  for (let bytes = 1; bytes <= 10000; bytes++) report(bytes, 10000);
  assert.equal(messages.length, 11);
  assert.match(messages.at(-1), /100%/);
});

test("release lookup failure preserves retry scope and never dispatches installation", async t => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error("network unavailable"); });
  let invoked = false;
  await assert.rejects(installRelease({version: "0.3.1", latest: false, args: ["--targets", "claude", "--dry-run"], write: () => {},
    run: () => { invoked = true; }}), /network unavailable[\s\S]*retry the same command, including any --targets or --dry-run options/);
  assert.equal(invoked, false);
});
