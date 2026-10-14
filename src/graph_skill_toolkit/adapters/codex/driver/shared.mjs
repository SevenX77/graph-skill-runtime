export const unsupported = message => ({ status: "unsupported", message });
export const responseResult = (response, success, status = "completed") => response?.isError
  ? { status: "error", message: "宿主接口返回错误。", data: response }
  : { status, message: success, data: response };

export const declared = (value, detail, extra = {}) => ({ state: value ? "available" : "unavailable", detail, ...extra });

// Internal/server errors may follow a host-side effect. Only a definite
// rejection or invalid request/method/params proves no update was accepted.
export const knownHostRejection = error => error?.outcome === "rejected" || [-32600, -32601, -32602].includes(error?.code);

export function writeContext(app, state, args, remove) {
  const operation = state.contextQueue.then(async () => {
    // An update may have reached the host even when its reply was lost. A later
    // full snapshot from stale local state could restore a removed key.
    if (state.contextUncertain) return { status: "rejected", message: "上一份页面上下文更新结果不明；请重建页面连接后再修改。" };
    const next = new Map(state.contexts);
    if (remove) next.delete(args.key); else next.set(args.key, structuredClone(args.content));
    let response;
    try { response = await app.updateModelContext({ structuredContent: { toolkitContext: Object.fromEntries(next) } }); }
    catch (error) {
      if (!knownHostRejection(error)) state.contextUncertain = true;
      throw error;
    }
    if (!response || typeof response !== "object" || Array.isArray(response)) {
      state.contextUncertain = true;
      throw new Error("宿主上下文更新回执不明；请重建页面连接后再修改。");
    }
    // updateModelContext acknowledges with an empty/meta result and throws on
    // rejection. An unexpected tool-style isError result cannot prove rollback.
    if (response.isError) {
      state.contextUncertain = true;
      throw new Error("宿主上下文更新返回非约定错误回执；效果不明，请重建页面连接后再修改。");
    }
    state.contexts = next;
    return { status: "completed", message: "已更新本模块的附加上下文；未提交消息。", data: { key: args.key, removed: remove, scope: "page-connection" } };
  });
  state.contextQueue = operation.then(() => {}, () => {});
  return operation;
}
