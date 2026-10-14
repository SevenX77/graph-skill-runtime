import assert from "node:assert/strict";
import { test } from "node:test";
import { createGraphRelay } from "../../backend/relay/index.mjs";

function fakeSource() {
  const listeners = new Map(), subscriptions = [];
  return {
    subscriptions,
    subscribe(root, receive) {
      subscriptions.push(root);
      listeners.set(root, receive);
      return () => { listeners.delete(root); subscriptions.push("unsubscribe:" + root); };
    },
    emit(root, event) { listeners.get(root)?.(event); },
    listening: root => listeners.has(root),
  };
}
const snapshot = id => ({ type: "snapshot", data: { graph: { id } } });

test("relay answers at once when the root's revision differs and waits for the next change otherwise", async () => {
  const source = fakeSource(), relay = createGraphRelay({ source, idleMs: 10 });
  const first = relay.wait("C:/skill", -1, 1000);
  source.emit("C:/skill", snapshot("one"));
  assert.deepEqual(await first, { revision: 1, event: snapshot("one") });
  assert.deepEqual(await relay.wait("C:/skill", 0, 1000), { revision: 1, event: snapshot("one") });
  const next = relay.wait("C:/skill", 1, 1000);
  source.emit("C:/skill", { type: "error", message: "broken" });
  assert.deepEqual(await next, { revision: 2, event: { type: "error", message: "broken" } });
  relay.close();
});

test("relay returns no event at its time limit or on abort and keeps one subscription per root", async () => {
  const source = fakeSource(), relay = createGraphRelay({ source, idleMs: 1000 });
  const warm = relay.wait("C:/skill", -1, 1000); source.emit("C:/skill", snapshot("one")); await warm;
  assert.deepEqual(await relay.wait("C:/skill", 1, 20), { revision: 1, event: null });
  const controller = new AbortController();
  const aborted = relay.wait("C:/skill", 1, 5000, controller.signal);
  controller.abort();
  assert.deepEqual(await aborted, { revision: 1, event: null });
  assert.deepEqual(source.subscriptions, ["C:/skill"]);
  relay.close();
  assert.equal(source.listening("C:/skill"), false);
  await assert.rejects(relay.wait("C:/skill", -1, 10), /closed/);
});

test("relay retires an idle root and resubscribes on the next wait", async () => {
  const source = fakeSource(), relay = createGraphRelay({ source, idleMs: 15 });
  const warm = relay.wait("C:/skill", -1, 1000); source.emit("C:/skill", snapshot("one")); await warm;
  await new Promise(resolve => setTimeout(resolve, 60));
  assert.equal(source.listening("C:/skill"), false);
  const again = relay.wait("C:/skill", 7, 1000); source.emit("C:/skill", snapshot("two"));
  assert.deepEqual(await again, { revision: 1, event: snapshot("two") });
  assert.deepEqual(source.subscriptions, ["C:/skill", "unsubscribe:C:/skill", "C:/skill"]);
  relay.close();
});
