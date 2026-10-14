import { declared, responseResult } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.message?.text, "向当前宿主会话提交指定消息；回执只确认受理");
export async function invoke(app, args) {
  const response = await app.sendMessage({ role: "user", content: [{ type: "text", text: args.text }] });
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    throw new Error("宿主消息提交回执无法确认受理；请检查会话，避免重复发送。");
  }
  return responseResult(response, "宿主已接受消息；实际会话效果需观察。", "accepted");
}
