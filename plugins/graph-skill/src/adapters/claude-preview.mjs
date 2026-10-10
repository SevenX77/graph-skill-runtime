import { lstat, mkdir, mkdtemp, readFile, realpath, rename, rmdir, unlink, writeFile } from "node:fs/promises";
import { join, isAbsolute } from "node:path";
import { createHash, randomUUID } from "node:crypto";

export const SNAPSHOT_SLOT = '<script id="graph-skill-snapshot" type="application/json">null</script>';
// Claude Desktop's local content preview rejects files larger than 512 KiB.
export const MAX_PREVIEW_BYTES = 524288;
const digest = value => createHash("sha256").update(value).digest("hex");

export function snapshotHtml(html, payload) {
  if (html.split(SNAPSHOT_SLOT).length !== 2) throw new Error("Canvas snapshot slot is missing or duplicated.");
  const data = JSON.stringify(payload).replace(/</g, "\\u003c");
  const output = html.replace(SNAPSHOT_SLOT, () => SNAPSHOT_SLOT.replace("null", () => data));
  if (Buffer.byteLength(output) > MAX_PREVIEW_BYTES) throw new Error("Claude local HTML preview exceeds its 512 KiB limit. Reduce the displayed root graph.");
  return output;
}

async function plainDirectory(path) {
  const stat = await lstat(path);
  if (!stat.isDirectory() || stat.isSymbolicLink() || await realpath(path) !== path) throw new Error(`Canvas directory must be a plain directory: ${path}`);
}

// One MCP process owns these temporary previews. No filesystem work at startup.
export function createClaudePreview(html, { report = message => console.error(message) } = {}) {
  const roots = new Map(), parents = new Set();
  let queue = Promise.resolve(), closed = false, closing;
  function serial(action) {
    const result = queue.then(action);
    queue = result.catch(() => {});
    return result;
  }
  async function check(view) {
    for (const path of view.parents) await plainDirectory(path);
    const info = await lstat(view.path);
    if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || digest(await readFile(view.path)) !== view.hash) throw new Error(`Canvas file changed outside its owner; preserved: ${view.path}`);
  }
  async function update(view, bytes) {
    await check(view);
    if (digest(bytes) === view.hash) return;
    const temporary = join(view.directory, `${randomUUID()}.tmp`);
    await writeFile(temporary, bytes, { flag: "wx", mode: 0o600 });
    try {
      await check(view);
      await rename(temporary, view.path);
      view.hash = digest(bytes);
    } finally {
      try { await check({ ...view, path: temporary, hash: digest(bytes) }); await unlink(temporary); }
      catch (error) { if (error.code !== "ENOENT") report(`Canvas temporary file preserved: ${error.message}`); }
    }
  }
  return {
    show(payload) {
      if (closed) return Promise.reject(new Error("Canvas session is closed."));
      return serial(async () => {
        const root = payload.skillRoot;
        if (typeof root !== "string" || !isAbsolute(root) || await realpath(root) !== root) throw new Error("HTML preview requires a canonical absolute Skill root.");
        const bytes = snapshotHtml(html, payload);
        let view = roots.get(root);
        if (view) await update(view, bytes);
        else {
          const chain = [root, join(root, ".gskill"), join(root, ".gskill", "canvas")];
          await plainDirectory(root);
          for (const path of chain.slice(1)) {
            try { await mkdir(path, { mode: 0o700 }); parents.add(path); }
            catch (error) { if (error.code !== "EEXIST") throw error; }
            await plainDirectory(path);
          }
          const directory = await mkdtemp(join(chain.at(-1), "view-"));
          view = { directory, parents: [...chain, directory], path: join(directory, "canvas.html"), hash: digest(bytes) };
          try { await writeFile(view.path, bytes, { flag: "wx", mode: 0o600 }); }
          catch (error) { await rmdir(directory); throw error; }
          roots.set(root, view);
        }
        return view.path;
      });
    },
    invalidate(root, message) {
      return serial(async () => {
        const view = roots.get(root);
        if (view) await update(view, snapshotHtml(html, { error: message }));
      });
    },
    close() {
      closed = true;
      return closing ??= serial(async () => {
        for (const view of roots.values()) {
          try { await check(view); await unlink(view.path); await rmdir(view.directory); }
          catch (error) { report(`Canvas cleanup preserved changed or inaccessible files: ${error.message}`); }
        }
        roots.clear();
        for (const path of [...parents].reverse()) {
          try { await plainDirectory(path); await rmdir(path); }
          catch (error) { if (!["ENOENT", "ENOTEMPTY", "EEXIST"].includes(error.code)) report(`Canvas cleanup preserved ${path}: ${error.message}`); }
        }
      });
    },
  };
}
