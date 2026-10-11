import { lstat, mkdir, open, realpath, rename, rmdir, unlink } from "node:fs/promises";
import { createHash, randomUUID } from "node:crypto";
import { isAbsolute, join } from "node:path";

const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const record = value => value !== null && typeof value === "object" && !Array.isArray(value);
const sameFile = (a, b) => a.dev === b.dev && a.ino === b.ino;
const sameRevision = (a, b) => sameFile(a, b) && a.size === b.size && a.mtimeNs === b.mtimeNs && a.ctimeNs === b.ctimeNs;
const entryBytes = entry => JSON.stringify(entry);

function originValue(value) {
  if (typeof value !== "string" || !/^http:\/\/127\.0\.0\.1:[1-9][0-9]{0,4}\/?$/.test(value)) throw new Error("Preview origin must be http://127.0.0.1:PORT with no path, credentials, query or fragment.");
  const port = Number(value.match(/:([0-9]+)\/?$/)[1]);
  if (port > 65535) throw new Error("Preview port must be between 1 and 65535.");
  return { url: `http://127.0.0.1:${port}`, port };
}

async function directory(path) {
  const info = await lstat(path);
  if (!info.isDirectory() || info.isSymbolicLink() || await realpath(path) !== path) throw new Error(`Preview configuration requires a plain canonical directory: ${path}`);
}

async function snapshot(path) {
  let before;
  try { before = await lstat(path, { bigint: true }); }
  catch (error) { if (error.code === "ENOENT") return null; throw error; }
  if (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1n || await realpath(path) !== path) throw new Error(`Preview configuration requires a plain single-link file: ${path}`);
  const file = await open(path, "r");
  try {
    const opened = await file.stat({ bigint: true });
    if (!sameRevision(before, opened)) throw new Error(`Preview configuration changed while opening: ${path}`);
    const bytes = await file.readFile();
    const after = await file.stat({ bigint: true });
    const current = await lstat(path, { bigint: true });
    if (!sameRevision(opened, after) || !sameRevision(after, current) || current.nlink !== 1n || current.isSymbolicLink() || await realpath(path) !== path) throw new Error(`Preview configuration changed while reading: ${path}`);
    return { bytes, hash: hash(bytes), info: after };
  } finally { await file.close(); }
}

async function unchanged(path, expected) {
  const actual = await snapshot(path);
  if (expected === null ? actual !== null : !actual || actual.hash !== expected.hash || !sameFile(actual.info, expected.info)) throw new Error(`Preview configuration changed outside its owner; preserved: ${path}`);
}

function documentValue(source) {
  if (!source) return { version: "0.0.1", configurations: [] };
  let value;
  try { value = JSON.parse(source.bytes.toString("utf8")); }
  catch { throw new Error("Existing .claude/launch.json is not valid JSON; preserved."); }
  if (!record(value) || (value.configurations !== undefined && !Array.isArray(value.configurations))) throw new Error("Existing launch.json must contain an object and a configurations array; preserved.");
  return { ...value, configurations: value.configurations ?? [] };
}

async function writeRevision(path, expected, bytes, parents, report) {
  for (const parent of parents) await directory(parent);
  await unchanged(path, expected);
  if (expected === null) {
    // wx is also an exclusive create against a non-cooperating file creator.
    const file = await open(path, "wx", 0o600);
    let written;
    try { await file.writeFile(bytes); await file.sync(); written = await file.stat({ bigint: true }); }
    finally { await file.close(); }
    for (const parent of parents) await directory(parent);
    const after = await snapshot(path);
    if (!after || after.hash !== hash(bytes) || !sameFile(after.info, written)) throw new Error(`Preview configuration changed after creation; preserved: ${path}`);
    return;
  }
  const temporary = join(parents.at(-1), `.graph-skill-preview-${randomUUID()}.tmp`);
  const file = await open(temporary, "wx", 0o600);
  try { await file.writeFile(bytes); await file.sync(); }
  finally { await file.close(); }
  const temporaryState = await snapshot(temporary);
  try {
    for (const parent of parents) await directory(parent);
    await unchanged(path, expected);
    await unchanged(temporary, temporaryState);
    await rename(temporary, path);
    const after = await snapshot(path);
    if (!after || after.hash !== hash(bytes) || !sameFile(after.info, temporaryState.info)) throw new Error(`Preview configuration changed after update; preserved: ${path}`);
  } finally {
    try { await unchanged(temporary, temporaryState); await unlink(temporary); }
    catch (error) {
      if (error.code !== "ENOENT" && await lstat(temporary).catch(() => null)) report(`Preview temporary file preserved: ${error.message}`);
    }
  }
}

/** Own only URL attach entries; the MCP process retains the HTTP server. */
export function createPreviewConfiguration({ report = message => console.error(message) } = {}) {
  const owned = new Map(), createdDirectories = new Set();
  let queue = Promise.resolve(), closed = false, closing;
  function serial(action) {
    const result = queue.then(action);
    queue = result.catch(() => {});
    return result;
  }
  async function locked(root, action) {
    await directory(root);
    const folder = join(root, ".claude");
    try { await mkdir(folder, { mode: 0o700 }); createdDirectories.add(folder); }
    catch (error) { if (error.code !== "EEXIST") throw error; }
    await directory(folder);
    const lockPath = join(folder, ".graph-skill-preview.lock");
    let lock;
    try { lock = await open(lockPath, "wx", 0o600); }
    catch (error) {
      if (error.code === "EEXIST") {
        await snapshot(lockPath); // Reject linked or non-regular lock occupants.
        throw new Error(`Preview configuration is busy: ${lockPath}. Wait for its owning operation, then retry; do not remove an active owner's lock.`);
      }
      throw error;
    }
    const lockBytes = Buffer.from(randomUUID());
    let lockState;
    try {
      await lock.writeFile(lockBytes); await lock.sync();
      lockState = await snapshot(lockPath);
      if (lockState.hash !== hash(lockBytes)) throw new Error("Preview lock changed outside its owner.");
      return await action({ folder, path: join(folder, "launch.json"), parents: [root, folder] });
    } finally {
      await lock.close();
      try {
        if (lockState) { await directory(folder); await unchanged(lockPath, lockState); await unlink(lockPath); }
      } catch (error) { report(`Preview configuration lock preserved: ${error.message}`); }
    }
  }
  return {
    ensure(projectRoot, origin) {
      if (closed) return Promise.reject(new Error("Preview configuration owner is closed."));
      return serial(async () => {
        if (typeof projectRoot !== "string" || !isAbsolute(projectRoot)) throw new Error("Preview project root must be an explicit canonical absolute path.");
        const endpoint = originValue(origin);
        return locked(projectRoot, async ({ path, parents }) => {
          const before = await snapshot(path), document = documentValue(before);
          let owner = owned.get(projectRoot);
          if (owner) {
            const matching = document.configurations.filter(item => item?.name === owner.entry.name);
            if (matching.length !== 1 || entryBytes(matching[0]) !== entryBytes(owner.entry)) throw new Error(`Owned preview entry was modified or removed; preserved: ${owner.entry.name}`);
            if (before.hash !== owner.lastWritten) owner.createdFile = false;
            if (owner.entry.url === endpoint.url) return { name: owner.entry.name, projectRoot };
          } else {
            const name = `graph-skill-${randomUUID()}`;
            if (document.configurations.some(item => item?.name === name)) throw new Error(`Preview configuration name is already occupied: ${name}`);
            owner = { createdFile: before === null, entry: { name, ...endpoint }, lastWritten: null };
          }
          const next = { name: owner.entry.name, ...endpoint };
          document.configurations = document.configurations.filter(item => item?.name !== owner.entry.name).concat(next);
          const bytes = Buffer.from(JSON.stringify(document, null, 2) + "\n");
          await writeRevision(path, before, bytes, parents, report);
          owner.entry = next; owner.lastWritten = hash(bytes); owned.set(projectRoot, owner);
          return { name: next.name, projectRoot };
        });
      });
    },
    close() {
      closed = true;
      return closing ??= serial(async () => {
        for (const [root, owner] of owned) {
          try {
            await locked(root, async ({ path, parents }) => {
              const before = await snapshot(path);
              if (!before) return;
              const document = documentValue(before);
              const matching = document.configurations.filter(item => item?.name === owner.entry.name);
              if (matching.length !== 1 || entryBytes(matching[0]) !== entryBytes(owner.entry)) {
                report(`Modified or missing preview entry preserved: ${owner.entry.name}`); return;
              }
              if (owner.createdFile && before.hash === owner.lastWritten) {
                for (const parent of parents) await directory(parent);
                await unchanged(path, before); await unlink(path);
              } else {
                document.configurations = document.configurations.filter(item => item?.name !== owner.entry.name);
                await writeRevision(path, before, Buffer.from(JSON.stringify(document, null, 2) + "\n"), parents, report);
              }
            });
          } catch (error) { report(`Preview configuration cleanup preserved files: ${error.message}`); }
        }
        owned.clear();
        for (const folder of createdDirectories) {
          try { await directory(folder); await rmdir(folder); }
          catch (error) { if (!["ENOENT", "ENOTEMPTY", "EEXIST"].includes(error.code)) report(`Preview configuration directory preserved: ${error.message}`); }
        }
        createdDirectories.clear();
      });
    },
  };
}
