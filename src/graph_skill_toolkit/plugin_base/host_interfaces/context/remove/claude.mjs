export const capability = () => ({ state: "available", detail: "移除当前连接设置的指定附加数据", scope: "page-connection" });
export async function invoke(_$, { state, owner, request, args }) {
  let context = state.contexts.get(owner);
  if (!context) { context = { scope: request.id, values: new Map() }; state.contexts.set(owner, context); }
  context.values.delete(args.key);
  return { status: "completed", message: "已更新本模块上下文，未提交消息。", data: { key: args.key, removed: true, scope: "page-connection" } };
}
