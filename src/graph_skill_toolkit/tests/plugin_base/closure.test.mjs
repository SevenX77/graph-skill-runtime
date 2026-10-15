import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { posix } from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const BASE = "plugin_base/";
// The Plugin Base surface: one entry per runtime plus the page entry's types.
const ENTRIES = new Set(["plugin_base/page/index.mjs", "plugin_base/page/types.ts", "plugin_base/server/index.mjs", "plugin_base/claude_mod/index.js"]);
const SKIP = new Set(["node_modules", "dist", "evidence", "tests", "build", ".git"]);
const CODE = /\.(mjs|js|cjs|ts|tsx)$/;
const SPECIFIER = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(["'])(\.{1,2}\/[^"']*)\1/g;

async function productionFiles(dir = "") {
  const files = [];
  for (const entry of await readdir(posix.join(root, dir), { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const path = dir ? `${dir}/${entry.name}` : entry.name;
    if (entry.isDirectory()) files.push(...await productionFiles(path));
    else if (CODE.test(entry.name)) files.push(path);
  }
  return files;
}

/** Resolve each relative import to a toolkit path; extensionless type imports keep their stem.
 * @param {Map<string,string>} sources path -> text */
export function closureViolations(sources) {
  const known = new Set(sources.keys());
  const resolve = (from, spec) => {
    const base = posix.normalize(posix.join(posix.dirname(from), spec));
    for (const ext of ["", ".ts", ".tsx", ".mjs", ".js"]) if (known.has(base + ext)) return base + ext;
    return base;
  };
  const violations = [];
  for (const [file, text] of sources) {
    for (const [, , spec] of text.matchAll(SPECIFIER)) {
      const target = resolve(file, spec);
      const inside = file.startsWith(BASE), targetInside = target.startsWith(BASE);
      if (inside && !targetInside) violations.push(`${file} imports ${target} outside the Plugin Base`);
      if (!inside && targetInside && !ENTRIES.has(target)) violations.push(`${file} imports Plugin Base internal ${target}`);
    }
  }
  return violations;
}

test("the Plugin Base is closed in both directions", async () => {
  const files = await productionFiles();
  const sources = new Map(await Promise.all(files.map(async file => [file, await readFile(posix.join(root, file), "utf8")])));
  assert.ok([...sources.keys()].some(file => file.startsWith(BASE)), "Plugin Base sources were found");
  assert.ok([...sources.keys()].some(file => file.startsWith("apps/")), "business sources were found");
  for (const entry of ENTRIES) assert.ok(sources.has(entry), `entry ${entry} exists`);
  assert.deepEqual(closureViolations(sources), []);
});

test("the closure check rejects an internal import and an outward import", () => {
  const sources = new Map([
    ["plugin_base/page/index.mjs", 'export { x } from "../adapters/x.mjs";'],
    ["plugin_base/adapters/x.mjs", 'import data from "../../apps/graph_canvas/data.mjs";'],
    ["apps/graph_canvas/data.mjs", 'import { x } from "../../plugin_base/page/index.mjs";'],
    ["apps/graph_canvas/leak.mjs", 'import { x } from "../../plugin_base/adapters/x.mjs";'],
  ]);
  assert.deepEqual(closureViolations(sources), [
    "plugin_base/adapters/x.mjs imports apps/graph_canvas/data.mjs outside the Plugin Base",
    "apps/graph_canvas/leak.mjs imports Plugin Base internal plugin_base/adapters/x.mjs",
  ]);
});
