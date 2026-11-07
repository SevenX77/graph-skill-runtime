import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, writeFile, rename, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createLocalHttpServer, createHostBridge } from "hostpane/server";
import { createGraphBackend } from "../../apps/graph_canvas/backend/graph/index.mjs";
import { createLiveGraphSource } from "../../apps/graph_canvas/application/live_source/index.mjs";
import { readGraphState } from "../../apps/graph_canvas/application/service/index.mjs";
import { fakeCompiler } from "../support/runtime.mjs";

const read = root => readGraphState(root, { compiler: fakeCompiler });
import { createGraphConnection, validateGraphBackend } from "../../apps/graph_canvas/application/client/index.mjs";

async function until(condition) {
  for (let i = 0; i < 100 && !condition(); i++) await new Promise(resolve => setTimeout(resolve, 10));
  assert.ok(condition(), "Expected local backend update did not arrive.");
}
const yaml = id => `schema_version: gskill.graph.v1\ngraph_id: ${id}\nphases:\n  - id: work\n    depends_on: [input]\n    output: true\n`;

test("shared frontend connects directly to local files, receives atomic saves and recovers without host calls", async () => {
  const root = await mkdtemp(join(tmpdir(), "local-app-live-"));
  const http = createLocalHttpServer();
  const backend = createGraphBackend({ http, source: createLiveGraphSource({ read, debounceMs: 5, reconcileMs: 10000 }) });
  let client;
  try {
    await mkdir(join(root, "phases", "work"), { recursive: true });
    await writeFile(join(root, "SKILL.md"), "# Skill\n");
    await writeFile(join(root, "phases", "work", "LOGIC.md"), "# Logic\n");
    await writeFile(join(root, "graph.yaml"), yaml("before"));
    await http.open();
    const authority = backend.createConnection();
    authority.select(root);
    client = createGraphConnection({ backend: authority.descriptor });
    const graphs = [], snapshots = [], errors = [], invalids = [];
    client.connect({ receive: value => { graphs.push(value.graph.id); snapshots.push(value); }, invalid: event => invalids.push(event), fail: error => errors.push(error) });
    client.selectRoot(root);
    await until(() => graphs.at(-1) === "before");
    await writeFile(join(root, "graph.yaml.tmp"), yaml("after"));
    await rename(join(root, "graph.yaml.tmp"), join(root, "graph.yaml"));
    await until(() => graphs.at(-1) === "after");
    await writeFile(join(root, "graph.yaml"), "invalid");
    await until(() => invalids.length === 1);
    assert.equal(invalids[0].diagnostics[0].code, "[F-test]");
    await writeFile(join(root, "graph.yaml"), yaml("restored"));
    await until(() => graphs.at(-1) === "restored");
    assert.deepEqual(graphs, ["before", "after", "restored"]);
    assert.equal(errors.length, 0);
    assert.equal(invalids.length, 1);
    await rename(join(root, "phases", "work", "LOGIC.md"), join(root, "phases", "work", "AGENT.md"));
    await until(() => snapshots.at(-1).graph.nodes.find(node => node.id === "work").kind === "AGENT");
    client.dispose();
    authority.close();
    assert.equal((await fetch(http.origin + "/graph/events?root=" + encodeURIComponent(root), { headers: { Authorization: "Bearer " + authority.descriptor.token } })).status, 401);
  } finally {
    client?.dispose(); backend.close(); await http.close(); await rm(root, { recursive: true, force: true });
  }
});

test("live source does not re-read on its own traversal, which would hold graph.yaml open against atomic saves", async () => {
  const root = await mkdtemp(join(tmpdir(), "local-app-self-read-"));
  let reads = 0;
  const source = createLiveGraphSource({ read: async value => { reads++; return read(value); }, debounceMs: 5, reconcileMs: 10000 });
  let unsubscribe;
  try {
    await mkdir(join(root, "phases", "work"), { recursive: true });
    await writeFile(join(root, "SKILL.md"), "# Skill\n");
    await writeFile(join(root, "phases", "work", "LOGIC.md"), "# Logic\n");
    await writeFile(join(root, "graph.yaml"), yaml("before"));
    const graphs = [];
    unsubscribe = source.subscribe(root, event => graphs.push(event.data?.graph.id));
    await until(() => graphs.at(-1) === "before");
    await new Promise(resolve => setTimeout(resolve, 200));
    assert.equal(reads, 1);
    await writeFile(join(root, "graph.yaml.tmp"), yaml("after"));
    await rename(join(root, "graph.yaml.tmp"), join(root, "graph.yaml"));
    await until(() => graphs.at(-1) === "after");
  } finally {
    unsubscribe?.(); source.close(); await rm(root, { recursive: true, force: true });
  }
});

test("one listener keeps cross-origin graph reads separate from same-origin host operations", async () => {
  const http = createLocalHttpServer();
  const backend = createGraphBackend({ http, source: createLiveGraphSource({ read }) });
  const host = createHostBridge({ http });
  try {
    await http.open();
    const graph = backend.createConnection(); graph.select(null);
    const view = await host.createView("/selected/skill");
    assert.equal(view.browser.url, http.origin);
    const preflight = await fetch(http.origin + "/graph/events", { method: "OPTIONS", headers: { Origin: "null", "Access-Control-Request-Headers": "authorization", "Access-Control-Request-Private-Network": "true" } });
    assert.equal(preflight.status, 204);
    assert.equal(preflight.headers.get("access-control-allow-origin"), "*");
    assert.equal(preflight.headers.get("access-control-allow-private-network"), "true");
    const headers = { Authorization: "Bearer " + graph.descriptor.token };
    assert.equal((await fetch(http.origin + "/graph/events?root=other", { headers })).status, 403);
    assert.equal((await fetch(http.origin + "/capabilities", { headers })).status, 401);
    assert.equal((await fetch(http.origin + "/graph/events", { headers: { Authorization: "Bearer " + view.browser.token } })).status, 401);
    assert.equal((await fetch(http.origin + "/capabilities", { headers: { Origin: "null", Authorization: "Bearer " + view.browser.token } })).status, 403);
    assert.throws(() => validateGraphBackend({ url: "https://remote.invalid", token: graph.descriptor.token }));
  } finally { backend.close(); await host.close(); await http.close(); }
});
