import { declared, responseResult } from "../../../adapters/codex/driver/shared.mjs";

// Explicit text invocation: https://learn.chatgpt.com/docs/app-server#skills
// This page submits the marker through ui/message; the host resolves the Skill.
const SKILL_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]*(?::[A-Za-z0-9][A-Za-z0-9_-]*)?$/;
const LIMIT = "通过当前会话的文本入口提交 $Skill名称 输入；宿主自行定位技能。回执只确认请求受理，技能是否找到、激活及执行结果需在对话中核对。";
const NAME_LIMIT = "此文本入口接受英文字母、数字、下划线和连字符组成的技能名称，也接受 插件名:技能名；每段以英文字母或数字开头，总长不超过 256 字符。";

export const capability = (host = {}) => declared(
  host.message?.text && typeof host.message.text === "object" && !Array.isArray(host.message.text),
  "向当前 Codex 会话提交 Skill 激活请求；回执只确认受理",
  { scope: "skill-activation-request", constraints: { inputTypes: ["string"], skillNamePattern: SKILL_NAME.source, skillNameMaxLength: 256 }, limits: [LIMIT, NAME_LIMIT] },
);

export async function invoke(app, args) {
  if (typeof args.skill !== "string" || args.skill.length > 256 || !SKILL_NAME.test(args.skill)) {
    return { status: "unsupported", message: NAME_LIMIT, evidence: { sent: null, limits: [NAME_LIMIT] } };
  }
  if (args.input !== undefined && typeof args.input !== "string") {
    return { status: "unsupported", message: "宿主 Skill 文本入口只接受字符串输入，不能转换其他 JSON 类型。", evidence: { sent: null } };
  }
  const params = { role: "user", content: [{ type: "text", text: "$" + args.skill + (args.input ? " " + args.input : "") }] };
  const response = await app.sendMessage(params);
  if (!response || typeof response !== "object" || Array.isArray(response) ||
      (response.isError !== undefined && typeof response.isError !== "boolean")) {
    throw new Error("宿主 Skill 请求回执无法确认受理；请检查对话，避免重复提交。");
  }
  return { ...responseResult(response, "Skill 激活请求已受理；技能是否找到、激活及执行结果需在对话中核对。", "accepted"),
    evidence: { sent: params, receipt: response, limits: [LIMIT] } };
}
