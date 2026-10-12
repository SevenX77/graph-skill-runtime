// @ts-check
/** The closed action vocabulary shared by the page, dispatcher and HTTP boundary. */
export const HOST_ACTIONS = Object.freeze(/** @type {const} */ ([
  "open-root", "open-file", "fill-prompt", "send-prompt",
  "update-context", "list-tools", "call-tool", "request-skill",
]));

/** @param {unknown} value @returns {Record<string, unknown>} */
function record(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("接口数据必须是对象。");
  return /** @type {Record<string, unknown>} */ (value);
}

/** @param {unknown} value @returns {import('./index').HostCapabilities} */
export function validateCapabilities(value) {
  const source = record(value);
  return Object.fromEntries(HOST_ACTIONS.map(action => {
    const item = source[action];
    if (item === undefined) return [action, { available: false, detail: "宿主未声明此能力。" }];
    const capability = record(item);
    if (typeof capability.available !== "boolean" || typeof capability.detail !== "string") throw new Error("适配器返回了无效能力说明。");
    return [action, { available: capability.available, detail: capability.detail }];
  }));
}

/** @param {unknown} value @returns {import('./index').HostResult} */
export function validateResult(value) {
  const result = record(value);
  if (typeof result.status !== "string" || !["completed", "accepted", "pending", "unsupported", "rejected", "error"].includes(result.status) ||
      typeof result.message !== "string" || (result.requestId !== undefined && typeof result.requestId !== "string")) {
    throw Object.assign(new Error("适配器返回了无效结果，无法确认操作状态。"),
      typeof result.requestId === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(result.requestId) ? { requestId: result.requestId } : {});
  }
  return /** @type {import('./index').HostResult} */ (value);
}

/** Validate against the currently displayed graph, and capture arguments before any await.
 * @param {import('./index').HostAction} action
 * @param {unknown} input
 * @param {import('../../ui/canvas/types').CanvasSnapshot | null} snapshot
 * @returns {import('./index').HostActionArgs}
 */
export function validateArguments(action, input, snapshot) {
  const args = record(input);
  const root = args.skillRoot;
  if (Object.keys(args).some(key => !["skillRoot", "text", "context"].includes(key))) throw new Error("未知的宿主操作参数。");
  if (typeof root !== "string" || !root || /[\0\r\n]/.test(root) || !(/^[A-Za-z]:[\\/]/.test(root) || root.startsWith("/")) || root !== snapshot?.skillRoot) {
    throw new Error("操作的 Skill 必须与当前画布的绝对路径一致。");
  }
  if (["fill-prompt", "send-prompt"].includes(action) && (typeof args.text !== "string" || !args.text.trim() || args.text.length > 8000)) throw new Error("消息须包含 1–8000 个字符。");
  if (args.text !== undefined && !["fill-prompt", "send-prompt"].includes(action)) throw new Error("此操作不接受消息参数。");
  if (args.context !== undefined || action === "update-context") {
    const context = record(args.context);
    if (action !== "update-context" || Object.keys(context).some(key => !["skillRoot", "graphId", "nodeId"].includes(key)) ||
        context.skillRoot !== root || context.graphId !== snapshot?.graph.id ||
        (context.nodeId !== undefined && !snapshot.graph.nodes.some(node => node.id === context.nodeId))) throw new Error("所选上下文与当前图或节点不符。");
  }
  return /** @type {import('./index').HostActionArgs} */ (/** @type {unknown} */ (structuredClone(args)));
}

/** @param {unknown} error @param {boolean} [dispatched] @returns {import('./index').HostResult} */
export function failureResult(error, dispatched = false) {
  const detail = error instanceof Error ? error.message : String(error);
  const info = error && typeof error === "object" ? /** @type {Record<string, unknown>} */ (error) : {};
  if (info.outcome === "rejected") return { status: "rejected", message: detail };
  if (info.outcome === "unknown" || (dispatched && info.outcome !== "not-sent")) return {
    status: "pending", message: `请求结果未知：${detail}。请检查宿主结果，避免重复发送。`,
    ...(typeof info.requestId === "string" ? { requestId: info.requestId } : {}),
  };
  return { status: "error", message: detail };
}
