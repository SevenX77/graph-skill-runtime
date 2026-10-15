import { contextText } from "../../../host_interfaces/context/update/index.mjs";
export const unsupported = message => ({ status: "unsupported", message });
export const responseResult = (response, success, status = "completed") => response?.isError
  ? { status: "error", message: "宿主接口返回错误。", data: response }
  : { status, message: success, data: response };

export const declared = (value, detail, extra = {}) => ({ state: value ? "available" : "unavailable", detail, ...extra });

// Internal/server errors may follow a host-side effect. Only a definite
// rejection or invalid request/method/params proves no update was accepted.
export const knownHostRejection = error => error?.outcome === "rejected" || [-32600, -32601, -32602].includes(error?.code);


// Each update replaces the page's whole snapshot, so a lost receipt cannot
// resurrect stale keys: the next update states the complete intended context.
export function writeContext(app, state, args, modalities = {}) {
  const operation = state.contextQueue.then(async () => {
    const empty = Object.keys(args.snapshot).length === 0;
    // Send only the modalities the host declared for model context.
    const params = empty ? (modalities.text ? { content: [] } : { structuredContent: {} }) : {
      ...(modalities.text ? { content: [{ type: "text", text: contextText(args.snapshot) }] } : {}),
      ...(modalities.structuredContent ? { structuredContent: structuredClone(args.snapshot) } : {}) };
    const response = await app.updateModelContext(params);
    if (!response || typeof response !== "object" || Array.isArray(response) || response.isError) {
      throw new Error("宿主上下文更新回执不明；当前快照是否生效需在下一轮核对。");
    }
    return { status: "completed", message: empty ? "已清空本页面上下文；未提交消息。" : "已替换本页面上下文快照；未提交消息。",
      data: { scope: "page-connection", cleared: empty }, evidence: { sent: params, receipt: response } };
  });
  state.contextQueue = operation.then(() => {}, () => {});
  return operation;
}
