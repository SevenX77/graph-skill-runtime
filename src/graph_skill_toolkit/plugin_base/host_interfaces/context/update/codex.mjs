import { declared, writeContext } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.updateModelContext?.text || host.updateModelContext?.structuredContent, "替换本页面的上下文快照；宿主在下一轮把它交给模型，不触发回复，用户不可见", {
  scope: "page-connection",
  limits: ["Codex 只确认收到快照；模型实际读到的内容无法从页面读回，请用“让模型复述上下文”核对。"],
});
export const invoke = (app, args, state) => writeContext(app, state, args, app.getHostCapabilities()?.updateModelContext ?? {});
