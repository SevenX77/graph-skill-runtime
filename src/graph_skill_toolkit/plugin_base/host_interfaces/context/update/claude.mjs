import { contextText } from "./index.mjs";
export const capability = () => ({ state: "available", detail: "替换本页面的上下文快照；下一条提交（任何来源）进入会话时，作为模型可见、用户不可见的上下文段落附上", scope: "page-connection",
  limits: ["Claude 在下一条提交时才附上快照；实际附上的段落由 context.attached 事件给出，请订阅事件核对。"] });
export async function invoke(_$, { state, owner, args }) {
  const snapshot = structuredClone(args.snapshot), empty = Object.keys(snapshot).length === 0;
  if (empty) state.contexts.delete(owner); else state.contexts.set(owner, { snapshot });
  return { status: "completed", message: empty ? "已清空本页面上下文；未提交消息。" : "已替换本页面上下文快照；下一条提交时附上，未提交消息。",
    data: { scope: "page-connection", cleared: empty }, evidence: { sent: { snapshot, attachAs: empty ? null : contextText(snapshot) } } };
}
