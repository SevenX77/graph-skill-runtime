import { unsupported } from "../../../adapters/codex/driver/shared.mjs";
export const capability = (_host, context = {}) => {
  const declared = Array.isArray(context.availableDisplayModes);
  const modes = declared ? context.availableDisplayModes.filter(mode => ["inline", "fullscreen", "pip"].includes(mode)) : [];
  return { state: !declared ? "unknown" : modes.length ? "available" : "unavailable", detail: "请求当前 MCP App 容器的显示模式，返回实际模式；不代表标签页焦点", scope: "current-app-container", constraints: { modes } };
};
export async function invoke(app, args, _state, cap) {
  if (!cap.constraints.modes.includes(args.mode)) return unsupported("宿主未声明请求的显示模式。");
  const response = await app.requestDisplayMode({ mode: args.mode });
  return response.mode === args.mode
    ? { status: "completed", message: "宿主返回了请求的显示模式；焦点和可见效果另行观察。", data: response }
    : { status: "rejected", message: "宿主返回不同的实际显示模式；请求的模式未设定。", data: response };
}
