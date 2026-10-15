export const capability = () => ({ state: "available", detail: "保存当前连接的附加数据，随后续提交送入模型上下文", scope: "page-connection" });
export async function invoke(_$, { state, owner, request, args }) {
  let context = state.contexts.get(owner);
  if (!context) { context = { scope: request.id, values: new Map() }; state.contexts.set(owner, context); }
  context.values.set(args.key, args.content);
  return { status: "completed", message: "已更新本模块上下文，未提交消息。", data: { key: args.key, removed: false, scope: "page-connection" } };
}
