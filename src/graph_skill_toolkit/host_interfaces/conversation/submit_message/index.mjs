import { text } from "../../validation/index.mjs";
export const definition = { id: "conversation.submitMessage", label: "提交消息", sample: { text: "请仅回复：接口消息测试成功。" }, fields: ["text"], validate(args) {
  if (!text(args.text)) throw new Error("消息须包含 1–8000 个字符。");
} };
