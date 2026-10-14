import { watch } from "node:fs";
import { skillFingerprint } from "../source/files.mjs";

// One filesystem owner per subscribed root. Watcher notifications are debounced
// for atomic/editor saves; reconciliation also catches missed filesystem events
// and phase-file edits the watcher filter skips. A stat-only fingerprint gates
// every read, so the costly runtime compile runs only when skill files changed.
// `read(root)` resolves to a snapshot or invalid event; a rejection becomes an
// error event.
export function createLiveGraphSource({ read, fingerprint = skillFingerprint, debounceMs = 75, reconcileMs = 1000, retainMs = 30000 }) {
  if (typeof read !== "function") throw new Error("Live graph source needs a read function.");
  const roots = new Map();
  let closed = false;
  function retire(entry) {
    entry.active = false;
    clearTimeout(entry.timer);
    clearTimeout(entry.retain);
    clearInterval(entry.reconcile);
    entry.watcher?.close();
    roots.delete(entry.root);
  }
  function create(root) {
    const entry = { root, active: true, listeners: new Set(), running: null, again: false, forceAgain: false, print: undefined, signature: "", event: null };
    const cycle = async force => {
      let print;
      try { print = root ? await fingerprint(root) : "demonstration"; }
      catch (error) { print = "unreadable:" + (error instanceof Error ? error.message : String(error)); }
      if (!force && print === entry.print) return;
      entry.print = print;
      let event;
      try { event = await read(root); }
      catch (error) { event = { type: "error", message: error instanceof Error ? error.message : String(error) }; }
      if (!entry.active) return;
      const signature = JSON.stringify(event);
      if (signature !== entry.signature) {
        entry.signature = signature;
        entry.event = event;
        for (const receive of entry.listeners) receive(event);
      }
    };
    // Resolves once no change remains unread, including changes that arrive mid-read.
    const refresh = (force = false) => {
      if (!entry.active) return Promise.resolve();
      if (entry.running) { entry.again = true; entry.forceAgain ||= force; return entry.running; }
      entry.running = (async () => {
        try {
          let next = force;
          do {
            entry.again = false; entry.forceAgain = false;
            await cycle(next);
            next = entry.forceAgain;
          } while (entry.again && entry.active);
        } finally { entry.running = null; }
      })();
      return entry.running;
    };
    if (root) {
      try {
        entry.watcher = watch(root, { recursive: true }, (event, filename) => {
          const path = filename?.toString().replaceAll("\\", "/");
          // Windows reports directory traversal as "change" on phase directories;
          // reacting to it would loop the fingerprint walk. Existence changes
          // arrive as "rename"; content edits of other files reach reconciliation.
          if (path && event === "change" && path !== "graph.yaml") return;
          if (path && path !== "SKILL.md" && path !== "graph.yaml" && path !== "phases" && path !== "subgraphs" && !path.startsWith("phases/") && !path.startsWith("subgraphs/")) return;
          clearTimeout(entry.timer);
          entry.timer = setTimeout(() => { void refresh(); }, debounceMs);
        });
        entry.watcher.on("error", () => { entry.watcher?.close(); entry.watcher = null; });
      } catch { /* Reconciliation remains active on filesystems without watch. */ }
      entry.reconcile = setInterval(() => { void refresh(); }, reconcileMs);
    }
    entry.refresh = refresh;
    return entry;
  }
  function enter(root) {
    if (closed) throw new Error("Graph source is closed.");
    let entry = roots.get(root);
    if (!entry) { entry = create(root); roots.set(root, entry); }
    clearTimeout(entry.retain);
    entry.retain = undefined;
    return entry;
  }
  // A root outlives its last listener for retainMs, so a page subscribing right
  // after show_graph reuses that call's compile result.
  function leave(entry) {
    if (entry.listeners.size || !entry.active) return;
    clearTimeout(entry.retain);
    entry.retain = setTimeout(() => { if (!entry.listeners.size) retire(entry); }, retainMs);
    entry.retain.unref?.();
  }
  return {
    subscribe(root, receive) {
      const entry = enter(root);
      entry.listeners.add(receive);
      if (entry.event) receive(entry.event);
      void entry.refresh();
      return () => {
        entry.listeners.delete(receive);
        leave(entry);
      };
    },
    /** The root's event after reading every change made before this call. */
    async current(root) {
      const entry = enter(root);
      const hold = () => {};
      entry.listeners.add(hold);
      try {
        await entry.refresh();
        return entry.event;
      } finally {
        entry.listeners.delete(hold);
        leave(entry);
      }
    },
    close() { closed = true; for (const entry of [...roots.values()]) retire(entry); },
  };
}
