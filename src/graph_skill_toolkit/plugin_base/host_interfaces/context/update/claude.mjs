import { contextText } from "./index.mjs";
export const capability = () => ({ state: "available", detail: "替换本页面上下文快照；其他来源的提交附上隐藏段落，本插件提交则在消息后附上用户可见的 JSON 段落", scope: "page-connection",
  limits: ["Claude 在下一条提交时附上快照；本插件消息中的快照在对话中可见，其他来源使用隐藏上下文；实际段落见 context.attached 事件。"] });
export async function invoke(_$, { state, owner, args }) {
  const snapshot = structuredClone(args.snapshot), empty = Object.keys(snapshot).length === 0;
  if (empty) state.contexts.delete(owner); else state.contexts.set(owner, { snapshot });
  return { status: "completed", message: empty ? "已清空本页面上下文；未提交消息。" : "已替换本页面上下文快照；下一条提交时附上，未提交消息。",
    data: { scope: "page-connection", cleared: empty }, evidence: { sent: { snapshot, attachAs: empty ? null : contextText(snapshot) } } };
}
