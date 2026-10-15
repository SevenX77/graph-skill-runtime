import assert from "node:assert/strict";
import { test } from "node:test";
import { createRelayGraphConnection } from "../../apps/graph_canvas/application/client/index.mjs";

const result = (revision, event) => ({ structuredContent: { revision, event } });
const snapshot = id => ({ type: "snapshot", data: { graph: { id }, skillRoot: "C:/skill" } });
const tick = () => new Promise(resolve => setTimeout(resolve, 0));

test("relay client long-polls watch_graph with the last revision and delivers snapshots, compile diagnostics and file errors", async () => {
  const invalidEvent = { type: "invalid", skillRoot: "C:/skill", diagnostics: [{ code: "[F-x]", severity: "fatal", message: "bad" }] };
  const calls = [], replies = [result(1, snapshot("one")), result(2, { type: "error", message: "broken" }), result(3, invalidEvent), result(3, null), result(4, snapshot("two"))];
  let release;
  const call = async (name, args) => { calls.push([name, args]); if (replies.length) return replies.shift(); await new Promise(resolve => { release = resolve; }); return result(4, null); };
  const received = [], failed = [], invalids = [];
  const connection = createRelayGraphConnection({ call, timeoutMs: 1234 });
  connection.connect({ receive: value => received.push(value.graph.id), invalid: event => invalids.push(event), fail: error => failed.push(error.message) });
  assert.equal(calls.length, 0);
  connection.selectRoot("C:/skill");
  for (let i = 0; i < 20 && calls.length < 6; i++) await tick();
  assert.deepEqual(received, ["one", "two"]);
  assert.deepEqual(failed, ["broken"]);
  assert.deepEqual(invalids, [invalidEvent]);
  assert.deepEqual(calls.map(([name, args]) => [name, args.after_revision]), [["watch_graph", undefined], ["watch_graph", 1], ["watch_graph", 2], ["watch_graph", 3], ["watch_graph", 3], ["watch_graph", 4]]);
  assert.ok(calls.every(([, args]) => args.skill_root === "C:/skill" && args.timeout_ms === 1234));
  connection.dispose(); release?.();
});

test("relay client retries transport failures, reports only a repeated failure, and stops on dispose or reselection", async () => {
  const calls = [];
  let mode = "fail";
  const call = async (name, args) => { calls.push(args.skill_root); if (mode === "fail") throw new Error("Select this Skill with show_graph before watching it."); return new Promise(() => {}); };
  const failed = [];
  const connection = createRelayGraphConnection({ call, retryMs: 5 });
  connection.connect({ receive: assert.fail, fail: error => failed.push(error.message) });
  connection.selectRoot("C:/skill");
  await new Promise(resolve => setTimeout(resolve, 30));
  assert.ok(calls.length >= 2);
  assert.deepEqual(failed, ["本地画布连接失败：Select this Skill with show_graph before watching it."]);
  mode = "hang";
  connection.selectRoot("C:/other");
  await tick();
  assert.equal(calls.at(-1), "C:/other");
  const count = calls.length;
  connection.dispose();
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(calls.length, count);
  connection.selectRoot("C:/third");
  await tick();
  assert.equal(calls.length, count, "a disposed connection starts no new poll");
});
