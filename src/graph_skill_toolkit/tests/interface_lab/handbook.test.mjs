import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { INTERFACES, LOCAL_DEFINITIONS } from "hostpane/page";
import { GUIDES } from "../../apps/interface_lab/application/guide.mjs";
import { QUICKSTART, operationAnchor } from "../../apps/interface_lab/application/handbook.mjs";
import { parseRoute, routeHash, switchMode, START, TRIGGER_VIEWS } from "../../apps/interface_lab/application/route.mjs";

const IDS = GUIDES.map(guide => guide.id);
const fallback = { mode: "guide", id: START };

test("the hash selects a mode and an operation, and anything else falls back", () => {
  assert.deepEqual(parseRoute("#lab/composer.writeDraft", IDS, fallback), { mode: "lab", id: "composer.writeDraft" });
  assert.deepEqual(parseRoute("#guide/start", IDS, fallback), { mode: "guide", id: START });
  assert.deepEqual(parseRoute("#guide/no.such", IDS, fallback), { mode: "guide", id: START });
  assert.deepEqual(parseRoute("#lab/start", IDS, fallback), { mode: "lab", id: IDS[0] });
  assert.deepEqual(parseRoute("", IDS, fallback), fallback);
  assert.deepEqual(parseRoute("#other", IDS, { mode: "lab", id: "tools.call" }), { mode: "lab", id: "tools.call" });
  assert.equal(routeHash({ mode: "lab", id: "tools.call" }), "#lab/tools.call");
  assert.deepEqual(parseRoute("#trigger/test", IDS, fallback), { mode: "trigger", id: "test" });
  assert.deepEqual(parseRoute("#trigger/tools.call", IDS, fallback), { mode: "trigger", id: TRIGGER_VIEWS[0] });
});

test("switching mode keeps the operation; the lab opens the first operation instead of the quick start", () => {
  assert.deepEqual(switchMode({ mode: "guide", id: "tools.call" }, "lab", IDS), { mode: "lab", id: "tools.call" });
  assert.deepEqual(switchMode({ mode: "guide", id: START }, "lab", IDS), { mode: "lab", id: IDS[0] });
  assert.deepEqual(switchMode({ mode: "lab", id: "tools.call" }, "guide", IDS), { mode: "guide", id: "tools.call" });
  assert.deepEqual(switchMode({ mode: "lab", id: "tools.call" }, "trigger", IDS), { mode: "trigger", id: "how" });
  assert.deepEqual(switchMode({ mode: "trigger", id: "rules" }, "guide", IDS), { mode: "guide", id: START });
  assert.deepEqual(switchMode({ mode: "trigger", id: "rules" }, "lab", IDS), { mode: "lab", id: IDS[0] });
});

test("every guided operation has Hostpane's field documentation and result summary", () => {
  const definitions = new Map([...INTERFACES, ...LOCAL_DEFINITIONS].map(item => [item.id, item]));
  for (const id of IDS) {
    const definition = definitions.get(id);
    assert.ok(definition, id);
    assert.ok(Array.isArray(definition.params) && definition.returns.trim(), id);
  }
});

test("every guide link names a heading that exists in the pinned Hostpane README", async () => {
  // The installed package is the pinned commit; its README is a file beside the package, outside the export map.
  const readme = await readFile(new URL("../../node_modules/hostpane/README.md", import.meta.url), "utf8");
  // GitHub's heading anchors: lower case, punctuation removed, spaces to hyphens.
  const anchors = new Set([...readme.matchAll(/^#{1,6} (.+)$/gm)].map(([, title]) => title.toLowerCase().replace(/[^\p{L}\p{N} -]/gu, "").replace(/ /g, "-")));
  for (const step of QUICKSTART.steps) assert.ok(anchors.has(step.anchor), step.anchor);
  for (const id of IDS) assert.ok(anchors.has(operationAnchor(id)), id);
});
