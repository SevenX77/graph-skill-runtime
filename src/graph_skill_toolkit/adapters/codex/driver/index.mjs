import { mcpCapabilities, operations } from "./registry.mjs";
import { knownHostRejection, unsupported } from "./shared.mjs";

/** A page-scoped Codex driver. The registry selects one interface module. */
export function codexAdapter(app, { originatingServer } = {}) {
  const state = { contexts: new Map(), contextQueue: Promise.resolve(), contextUncertain: false, originatingServer };
  return {
    async invoke(action, args = {}) {
      const cap = mcpCapabilities(app.getHostCapabilities(), app.getHostContext?.())[action];
      if (cap?.state !== "available") return unsupported(cap?.detail || "当前接入尚未确认此原生接口。");
      const operation = operations[action];
      if (!operation) return unsupported("当前连接没有此原生执行接口。");
      try { return await operation.invoke(app, args, state, cap); }
      catch (error) {
        // Only explicit rejection and invalid request/method/params prove no host update.
        if (knownHostRejection(error)) error.outcome = "rejected";
        throw error;
      }
    },
  };
}
