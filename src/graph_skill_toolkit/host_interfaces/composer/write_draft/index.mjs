import { text } from "../../validation/index.mjs";
export const definition = { id: "composer.writeDraft", label: "写入草稿", sample: { text: "接口草稿测试", mode: "append" }, fields: ["text", "mode"], validate(args) {
  if (!text(args.text)) throw new Error("消息须包含 1–8000 个字符。");
  if (!["append", "replace"].includes(args.mode)) throw new Error("草稿模式必须为 append 或 replace。");
} };
