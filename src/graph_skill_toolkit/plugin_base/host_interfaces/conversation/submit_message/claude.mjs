import { sourceOf } from "./index.mjs";
import { contextText } from "../../context/update/index.mjs";
import { queueEvent } from "../../../adapters/claude/mod/lifecycle/index.mjs";
const DEFAULT_LIMIT = "Claude 宿主的新会话默认模型和 effort 没有已确认的读取方法；要求“默认”会返回不支持。";
const TURN_LIMIT = "指定的模型和 effort 只作用于这条消息开启的一轮主对话，不改会话设置；实际采用值见 turn.completed 事件的 override.applied。";
export const capability = () => ({ state: "available", detail: "调用 Mod 消息提交接口，等待当前会话空闲后处理；本页面快照在消息后以可见 JSON 段落附上",
  constraints: { modelSources: ["current", "specified"], effortSources: ["current", "specified"] }, limits: [DEFAULT_LIMIT, TURN_LIMIT] });
export async function invoke($, { state, args, guard, request, owner }) {
  if (sourceOf(args.model) === "default" || sourceOf(args.effort) === "default") return { status: "unsupported", message: DEFAULT_LIMIT, evidence: { sent: null, limits: [DEFAULT_LIMIT] } };
  const snapshot = state.contexts.get(owner)?.snapshot;
  const blocks = snapshot && Object.keys(snapshot).length ? [contextText(snapshot)] : [];
  const text = args.text + blocks.map(block => "\n\n---\n" + block).join("");
  const sent = { text: args.text, inlinedContext: blocks };
  const override = (sourceOf(args.model) === "specified" || sourceOf(args.effort) === "specified")
    ? { requestId: request.id, text, ...(args.model?.source === "specified" ? { model: args.model.value } : {}), ...(args.effort?.source === "specified" ? { effort: args.effort.value } : {}) }
    : null;
  await guard();
  const sessionModel = await $.session.model();
  if (override) state.overrides.push(override);
  const response = await $.prompt.submit({ text });
  // A missing or malformed receipt does not prove that the prompt was refused.
  // The bridge will retain an unknown outcome; it must never submit it again.
  if (typeof response?.drop === "string") {
    if (override) state.overrides.splice(state.overrides.indexOf(override), 1);
    return { status: "rejected", message: "宿主拒绝消息提交。", data: { reason: response.drop }, evidence: { sent, receipt: response } };
  }
  if (typeof response?.text !== "string") throw new Error("宿主消息提交回执无法确认受理；请检查会话，避免重复发送。");
  const modified = response.text !== text;
  if (blocks.length) queueEvent(state, "context.attached", { blocks, origin: "plugin-inline" });
  return {
    status: "accepted",
    message: modified ? "宿主已受理经钩子改写的消息；请检查实际内容。" : "消息提交已受理；模型回复在对话中观察。",
    data: { modified },
    evidence: { sent, receipt: response, observed: { contextDelivery: blocks.length ? "inline" : null, sessionModel, turnOverride: override ? { model: override.model ?? null, effort: override.effort ?? null, turnId: override.turnId ?? null } : null },
      limits: override ? [TURN_LIMIT] : [] },
  };
}
