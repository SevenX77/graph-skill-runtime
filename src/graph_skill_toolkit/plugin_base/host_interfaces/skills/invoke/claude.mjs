export const capability = () => ({ state: "available", detail: "提交 /Skill名称 输入 的斜杠命令；等待会话空闲，激活与回复在对话中可见", scope: "skill-activation", constraints: { inputTypes: ["string"] } });

export async function invoke($, { args, guard }) {
  if (args.input !== undefined && typeof args.input !== "string") return { status: "unsupported", message: "宿主 Skill 入口只接受字符串输入，不能转换其他 JSON 类型。" };
  const text = "/" + args.skill + (args.input ? " " + args.input : "");
  await guard();
  const response = await $.prompt.submit({ text });
  if (typeof response?.drop === "string") return { status: "rejected", message: "宿主拒绝 Skill 命令提交。", data: { reason: response.drop }, evidence: { sent: { text }, receipt: response } };
  if (typeof response?.text !== "string") throw new Error("宿主 Skill 命令回执无法确认受理；请检查对话，避免重复提交。");
  return { status: "accepted", message: "Skill 斜杠命令已受理；激活与回复在对话及下一次 turn.completed 事件中观察。",
    evidence: { sent: { text }, receipt: response, observed: { activation: "conversation-and-next-turn.completed" } } };
}
