export const capability = () => ({ state: "available", detail: "调用 Mod 消息提交接口，等待当前会话空闲后处理" });
export async function invoke($, { state, owner, args, guard }) {
  const context = state.contexts.get(owner);
  const text = args.text + (context?.values.size ? "\n\nToolkit context supplied as data: " + JSON.stringify(Object.fromEntries(context.values)) : "");
  await guard();
  const response = await $.prompt.submit({ text });
  // A missing or malformed receipt does not prove that the prompt was refused.
  // The bridge will retain an unknown outcome; it must never submit it again.
  if (typeof response?.drop === "string") return {
    status: "rejected", message: "宿主拒绝消息提交。", data: { reason: response.drop },
  };
  if (typeof response?.text !== "string") throw new Error("宿主消息提交回执无法确认受理；请检查会话，避免重复发送。");
  const modified = response.text !== text;
  return {
    status: "accepted",
    message: modified ? "宿主已受理经钩子改写的消息；请检查实际内容。" : "消息提交已受理；任务结果由当前会话呈现。",
    data: { modified },
  };
}
