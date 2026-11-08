import test from "node:test";
import assert from "node:assert/strict";
import { access, readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { posix } from "node:path";

// The toolkit builds on Hostpane, the separately versioned host-integration
// package, and reaches it only through its five public entries.
const root = fileURLToPath(new URL("../../", import.meta.url));
const ENTRIES = new Set(["hostpane/page", "hostpane/page/types", "hostpane/server", "hostpane/claude-mod", "hostpane/triggers"]);
const SKIP = new Set(["node_modules", "dist", "evidence", "build", ".git"]);
const CODE = /\.(mjs|js|cjs|ts|tsx)$/;
const SPECIFIER = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|\bimport\(\s*)(["'])([^"']+)\1/g;

async function codeFiles(dir = "") {
  const files = [];
  for (const entry of await readdir(posix.join(root, dir), { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const path = dir ? `${dir}/${entry.name}` : entry.name;
    if (entry.isDirectory()) files.push(...await codeFiles(path));
    else if (CODE.test(entry.name)) files.push(path);
  }
  return files;
}

/** @param {Map<string,string>} sources path -> text */
export function boundaryViolations(sources) {
  const violations = [];
  for (const [file, text] of sources) {
    for (const [, , spec] of text.matchAll(SPECIFIER)) {
      if ((spec === "hostpane" || spec.startsWith("hostpane/")) && !ENTRIES.has(spec)) violations.push(`${file} imports ${spec}, which is not a Hostpane entry`);
      if (/(^|\/)node_modules\/hostpane\//.test(spec)) violations.push(`${file} reaches into node_modules/hostpane`);
      if (/(^|\/)plugin_base\//.test(spec)) violations.push(`${file} imports ${spec} from a plugin_base/ directory`);
    }
  }
  return violations;
}

test("toolkit code and tests reach Hostpane only through its four entries", async () => {
  // This file holds rejected samples as text; it is checked by the last test instead.
  const files = (await codeFiles()).filter(file => file !== "tests/graph/hostpane-boundary.test.mjs");
  const sources = new Map(await Promise.all(files.map(async file => [file, await readFile(posix.join(root, file), "utf8")])));
  assert.ok([...sources.values()].some(text => text.includes('"hostpane/server"') || text.includes("'hostpane/server'")), "toolkit code imports Hostpane");
  assert.deepEqual(boundaryViolations(sources), []);
  await assert.rejects(access(posix.join(root, "plugin_base")), "no plugin_base/ directory remains in the toolkit");
});

test("the toolkit pins Hostpane by one exact commit", async () => {
  const manifest = JSON.parse(await readFile(posix.join(root, "package.json"), "utf8"));
  assert.match(manifest.dependencies.hostpane, /^git\+https:\/\/github\.com\/SevenX77\/hostpane\.git#[0-9a-f]{40}$/);
});

test("the boundary check rejects a deep import, a node_modules path and a plugin_base path", () => {
  const sources = new Map([
    ["apps/a.mjs", 'import { x } from "hostpane/server";\nimport { y } from "hostpane/src/adapters/x.mjs";'],
    ["apps/b.mjs", 'import { z } from "../node_modules/hostpane/src/page/index.mjs";'],
    ["tests/c.mjs", 'import { w } from "../../plugin_base/page/index.mjs";'],
  ]);
  assert.deepEqual(boundaryViolations(sources), [
    "apps/a.mjs imports hostpane/src/adapters/x.mjs, which is not a Hostpane entry",
    "apps/b.mjs reaches into node_modules/hostpane",
    "tests/c.mjs imports ../../plugin_base/page/index.mjs from a plugin_base/ directory",
  ]);
});
