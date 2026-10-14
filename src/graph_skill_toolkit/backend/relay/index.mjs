// Long-poll delivery of live graph events for pages that reach the backend only
// through a request/response channel (the Codex MCP App relay). One revision
// counter per root sits on the shared live source; waiters resolve on the next
// change or at their time limit. A root with no waiter retires after idleMs.
export function createGraphRelay({ source, idleMs = 60000, clock = { setTimeout, clearTimeout } }) {
  const roots = new Map();
  let closed = false;

  function enter(root) {
    let entry = roots.get(root);
    if (!entry) {
      entry = { revision: 0, event: null, waiters: new Set(), idle: undefined, unsubscribe: () => {} };
      const current = entry;
      roots.set(root, current);
      current.unsubscribe = source.subscribe(root, event => {
        current.revision += 1;
        current.event = event;
        for (const wake of [...current.waiters]) wake();
      });
    }
    clock.clearTimeout(entry.idle);
    entry.idle = undefined;
    return entry;
  }

  function leave(root, entry) {
    if (entry.waiters.size || roots.get(root) !== entry) return;
    clock.clearTimeout(entry.idle);
    entry.idle = clock.setTimeout(() => {
      if (entry.waiters.size || roots.get(root) !== entry) return;
      roots.delete(root);
      entry.unsubscribe();
    }, idleMs);
  }

  const answer = (entry, afterRevision) =>
    entry.event && entry.revision !== afterRevision ? { revision: entry.revision, event: entry.event } : null;

  return {
    /** Resolve with the root's current event once its revision differs from
     * afterRevision, or with `event: null` when timeoutMs or the signal ends the wait. */
    async wait(root, afterRevision, timeoutMs, signal) {
      if (closed) throw new Error("Graph relay is closed.");
      const entry = enter(root);
      try {
        const ready = answer(entry, afterRevision);
        if (ready) return ready;
        return await new Promise(resolve => {
          let timer;
          const finish = () => {
            clock.clearTimeout(timer);
            entry.waiters.delete(finish);
            signal?.removeEventListener?.("abort", finish);
            resolve(answer(entry, afterRevision) ?? { revision: entry.revision, event: null });
          };
          entry.waiters.add(finish);
          timer = clock.setTimeout(finish, timeoutMs);
          if (signal?.aborted) finish();
          else signal?.addEventListener?.("abort", finish, { once: true });
        });
      } finally {
        leave(root, entry);
      }
    },
    close() {
      closed = true;
      for (const entry of roots.values()) {
        clock.clearTimeout(entry.idle);
        entry.unsubscribe();
        for (const wake of [...entry.waiters]) wake();
      }
      roots.clear();
    },
  };
}
