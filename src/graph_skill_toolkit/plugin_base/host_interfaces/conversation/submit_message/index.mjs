import { record, string, text } from "../../validation/index.mjs";

export const EFFORTS = Object.freeze(["low", "medium", "high", "xhigh", "max"]);
/** Model or effort selection: the current session's setting, the host default, or a named value. */
function selection(value, kind) {
  if (value === undefined) return;
  const item = record(value);
  if (Object.keys(item).some(key => !["source", "value"].includes(key)) || !["current", "default", "specified"].includes(item.source)) throw new Error(`${kind} 的 source 必须是 current、default 或 specified。`);
  if (item.source === "specified" ? !string(item.value) : item.value !== undefined) throw new Error(`${kind} 只有 specified 时提供 value。`);
  if (kind === "effort" && item.source === "specified" && !EFFORTS.includes(item.value)) throw new Error(`effort 必须是 ${EFFORTS.join("、")} 之一。`);
}
export const definition = { id: "conversation.submitMessage", label: "提交消息", sample: { text: "请仅回复：接口消息测试成功。", model: { source: "current" }, effort: { source: "current" } }, fields: ["text", "model", "effort"], validate(args) {
  if (!text(args.text)) throw new Error("消息须包含 1–8000 个字符。");
  selection(args.model, "model");
  selection(args.effort, "effort");
} };
/** Requested source of a selection, `current` when omitted. */
export const sourceOf = value => value?.source ?? "current";
