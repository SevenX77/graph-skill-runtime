import assert from "node:assert/strict";
import test from "node:test";
import { GUIDES } from "../../apps/interface_lab/application/guide.mjs";
import { contextReadout, recordPath, runOperation, workspaceRoot, localTime } from "../../apps/interface_lab/application/runner.mjs";
import { HOST_ACTIONS, validateArguments, LOCAL_ACTIONS, validateLocalArguments } from "hostpane/page";

const lab = { stateDirectory: "C:\\lab", sandbox: "C:\\lab\\sandbox", records: "C:\\lab\\records", sampleFile: "C:\\lab\\sandbox\\sample.txt" };

test("the lab guides every host interface and local capability exactly once", () => {
  assert.deepEqual(GUIDES.map(guide => guide.id), [...HOST_ACTIONS, ...LOCAL_ACTIONS]);
  for (const guide of GUIDES) {
    assert.ok(guide.purpose && guide.expect.claude && guide.expect.codex && guide.check, guide.id);
    assert.ok(guide.presets.length, guide.id);
  }
});

test("every preset is valid input for its operation on both hosts", () => {
  for (const guide of GUIDES) for (const preset of guide.presets) for (const host of ["claude", "codex"]) {
    const args = preset.args({ lab, host, lastViewId: "view-1", workspaceRoot: "C:/workspace" });
    if (guide.kind === "local") validateLocalArguments(guide.id, args);
    else validateArguments(guide.id, args);
  }
});

test("the Codex message guidance states that model and effort cannot be specified", () => {
  const guide = GUIDES.find(item => item.id === "conversation.submitMessage");
  assert.match(guide.expect.codex, /没有模型和 effort 字段/);
});

test("context readout shows the exact text each host sends", () => {
  assert.deepEqual(contextReadout({ status: "completed", message: "", evidence: { sent: { attachAs: "Plugin page context: {}" } } }), ["Plugin page context: {}"]);
  assert.deepEqual(contextReadout({ status: "completed", message: "", evidence: { sent: { content: [{ type: "text", text: "Plugin page context: {\"a\":1}" }], structuredContent: { a: 1 } } } }), ["Plugin page context: {\"a\":1}"]);
  assert.deepEqual(contextReadout({ status: "completed", message: "" }), []);
});

test("records are named per host and session start with the directory's separator", () => {
  assert.equal(recordPath("C:\\lab\\records", "codex", "2026-10-14T01:02:03.456Z"), "C:\\lab\\records\\codex-2026-10-14T01-02-03-456Z.json");
  assert.equal(recordPath("/state/records/", "claude", "2026-10-14T01:02:03.456Z"), "/state/records/claude-2026-10-14T01-02-03-456Z.json");
});

test("the runner sends host interfaces to invoke, local capabilities to local, and runs subscriptions live", async () => {
  const calls = [], listeners = [];
  const adapter = {
    invoke: async (action, args) => { calls.push(["invoke", action, args]); return { status: "completed", message: "ok" }; },
    capabilities: async () => ({ "events.subscribe": { state: "available", detail: "d", constraints: { types: ["tool.completed"] }, limits: ["l"] } }),
    events: { subscribe: (listener, types) => { listeners.push([listener, types]); return () => calls.push(["unsubscribe"]); } },
    local: {
      call: async (operation, args) => { calls.push(["local", operation, args]); return { status: "completed", message: "ok" }; },
      files: { watch: async (args, listener) => { listeners.push([listener, args]); return { status: "completed", message: "ok", data: { watchId: "w-1" }, stop: async () => ({ status: "completed", message: "stopped" }) }; } },
    },
  };
  const seen = [];
  await runOperation(adapter, "composer.writeDraft", { text: "x", mode: "append" }, () => {});
  await runOperation(adapter, "local.files.read", { path: "C:/a" }, () => {});
  const watched = await runOperation(adapter, "local.files.watch", { paths: ["C:/a"] }, (event, source) => seen.push([event.type, source]));
  assert.equal(typeof watched.stop, "function");
  const subscribed = await runOperation(adapter, "events.subscribe", { types: ["tool.completed", "turn.completed"] }, (event, source) => seen.push([event.type, source]));
  assert.deepEqual(subscribed.result.evidence.observed.requestedButNotDeliverable, ["turn.completed"]);
  listeners[1][0]({ type: "tool.completed", at: "t" });
  assert.match(subscribed.stop().message, /收到 1 个事件/);
  assert.deepEqual(calls.slice(0, 2), [["invoke", "composer.writeDraft", { text: "x", mode: "append" }], ["local", "local.files.read", { path: "C:/a" }]]);
  assert.deepEqual(seen, [["tool.completed", "events.subscribe"]]);
});


test("host-file presets use the session workspace while local presets keep the sandbox", () => {
  for (const root of ["C:/project with spaces/中文", "C:\\project with spaces\\中文", "/workspace/project/"]) {
    const context = { lab, host: "claude", lastViewId: null, workspaceRoot: root };
    const file = GUIDES.find(item => item.id === "files.openFile").presets[0].args(context);
    assert.equal(file.path.replaceAll("\\", "/"), root.replaceAll("\\", "/").replace(/\/$/, "") + "/README.md");
    assert.equal(file.line, undefined);
    assert.equal(GUIDES.find(item => item.id === "files.openFile").presets[1].args(context).line, 2);
    assert.equal(GUIDES.find(item => item.id === "files.revealDirectory").presets[0].args(context).path, root);
    assert.equal(GUIDES.find(item => item.id === "local.files.read").presets[0].args(context).path, lab.sampleFile);
  }
});

test("lab workspace reads workspaceRoots first and cwd only as fallback", () => {
  const reply = data => ({ status: "completed", message: "ok", data });
  assert.equal(workspaceRoot(reply({ workspaceRoots: ["C:/root"], cwd: "C:/cwd" })), "C:/root");
  assert.equal(workspaceRoot(reply({ workspaceRoots: [], cwd: "C:/cwd" })), "C:/cwd");
  assert.equal(workspaceRoot(reply({})), null);
});

test("context clear preset sends the required empty snapshot envelope", () => {
  const clear = GUIDES.find(item => item.id === "context.update").presets.find(item => item.label === "清空");
  assert.deepEqual(clear.args({ lab, host: "claude", lastViewId: null }), { snapshot: {} });
  assert.throws(() => validateArguments("context.update", {}));
});

test("lab run cards and events share a local time with zone indication", () => {
  const at = "2026-10-16T05:53:51.286Z";
  assert.equal(localTime(at), new Date(at).toLocaleTimeString(undefined, { timeZoneName: "short" }));
});


test("unknown workspace and lab paths never become executable example paths", () => {
  const context = { lab: null, host: "codex", lastViewId: null, workspaceRoot: null };
  for (const id of ["files.openFile", "files.revealDirectory", "local.files.read", "local.files.write", "local.system.revealInFileManager"]) {
    const guide = GUIDES.find(item => item.id === id);
    assert.equal(guide.presets[0].args(context).path, "", id);
  }
});
