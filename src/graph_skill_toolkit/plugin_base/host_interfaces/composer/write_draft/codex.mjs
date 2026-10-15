import { declared, responseResult, unsupported } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.message?.text && host.experimental?.["openai/message"]?.draft, "追加输入框草稿，不提交消息", { constraints: { modes: ["append"] } });
export async function invoke(app, args) {
  if (args.mode !== "append") return unsupported("当前草稿扩展只支持已声明的 append 模式。");
  const response = await app.sendMessage({ role: "user", content: [{ type: "text", text: args.text }],
    _meta: { "openai/message": { target: "active", send: false } } });
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    throw new Error("宿主草稿回执无法确认受理；请检查输入框，避免重复写入。");
  }
  return responseResult(response, "宿主已接受草稿请求；输入框效果需观察。", "accepted");
}
