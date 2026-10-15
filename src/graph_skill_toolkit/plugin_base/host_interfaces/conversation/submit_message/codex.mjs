import { declared, responseResult } from "../../../adapters/codex/driver/shared.mjs";
import { sourceOf } from "./index.mjs";
const LIMIT = "Codex MCP App 的 sendMessage 只有角色和内容字段，没有模型和 effort 字段：消息使用当前会话的模型和 effort；要求“指定”或“默认”会返回不支持。";
export const capability = host => declared(host.message?.text, "向当前宿主会话提交指定消息；回执只确认受理", {
  constraints: { modelSources: ["current"], effortSources: ["current"] }, limits: [LIMIT],
});
export async function invoke(app, args) {
  const params = { role: "user", content: [{ type: "text", text: args.text }] };
  if (sourceOf(args.model) !== "current" || sourceOf(args.effort) !== "current") {
    return { status: "unsupported", message: LIMIT, evidence: { sent: null, limits: [LIMIT] } };
  }
  const response = await app.sendMessage(params);
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    throw new Error("宿主消息提交回执无法确认受理；请检查会话，避免重复发送。");
  }
  return { ...responseResult(response, "宿主已接受消息；模型回复在对话中观察。", "accepted"), evidence: { sent: params, receipt: response } };
}
