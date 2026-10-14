import { callNative } from "../../../adapters/claude/mod/operations/tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";

export const capability = tools => present(has(tools, "Skill"), "调用当前会话的原生 Skill 工具；仅工具清单不保证指定 Skill 可用", { scope: "skill-activation", constraints: { inputTypes: ["string"] } });

export async function invoke($, { tools, args, guard }) {
  if (args.input !== undefined && typeof args.input !== "string") return { status: "unsupported", message: "宿主 Skill 入口只接受字符串输入，不能转换其他 JSON 类型。" };
  await guard();
  const called = await callNative($, tools, "Skill", { skill: args.skill, ...(args.input !== undefined ? { args: args.input } : {}) });
  if (called.status !== "completed") return called;

  // The native call's resolution proves only that a tool responded. Its Skill
  // result must establish activation separately; business work is not inferred.
  const receipt = called.data?.result;
  if (receipt?.success === false) return { status: "error", message: "宿主 Skill 工具报告激活失败。", data: called.data };
  if (receipt?.success !== true || typeof receipt.commandName !== "string" || !receipt.commandName) {
    return { status: "pending", message: "宿主 Skill 工具已返回，但缺少可确认激活的原生回执；请核对宿主结果，不要重试。", data: called.data };
  }
  if (receipt.status === "forked" && receipt.background === true) {
    return { status: "accepted", message: "宿主报告 Skill 后台任务已启动；业务结果仍待另行核对。", data: called.data };
  }
  return { status: "completed", message: receipt.readOnly === true
    ? "宿主已只读加载 Skill 指令；未执行 Skill 业务任务。"
    : "宿主报告 Skill 已激活；业务任务结果须另行核对。", data: called.data };
}
