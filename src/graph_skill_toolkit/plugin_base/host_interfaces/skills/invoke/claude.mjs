export const capability = () => ({ state: "available", detail: "以插件身份运行 /Skill名称 输入 的斜杠命令；等待会话空闲，激活与回复在对话中可见", scope: "skill-activation", constraints: { inputTypes: ["string"] } });

export async function invoke($, { args, guard }) {
  if (args.input !== undefined && typeof args.input !== "string") return { status: "unsupported", message: "宿主 Skill 入口只接受字符串输入，不能转换其他 JSON 类型。" };
  const sent = { command: args.skill, ...(args.input ? { args: args.input } : {}) };
  const commands = await $.command.list();
  if (!commands.some(command => command.name === args.skill)) return { status: "rejected", message: "当前会话的斜杠命令清单里没有这个 Skill。", data: { failureScope: "request" }, evidence: { sent, receipt: null } };
  await guard();
  const response = await $.command.run(sent);
  return { status: "accepted", message: "Skill 斜杠命令已运行；激活与回复在对话及下一次 turn.completed 事件中观察。",
    evidence: { sent, receipt: response ?? null, observed: { activation: "conversation-and-next-turn.completed" } } };
}
