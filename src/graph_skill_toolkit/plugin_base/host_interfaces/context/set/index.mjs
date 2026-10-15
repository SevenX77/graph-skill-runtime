import { string } from "../../validation/index.mjs";
export const definition = { id: "context.set", label: "设置上下文", sample: { key: "example", content: { value: "context-test" } }, fields: ["key", "content"], validate(args) {
  if (!string(args.key) || ["__proto__", "constructor", "prototype"].includes(args.key)) throw new Error("无效的上下文 key。");
  if (!Object.hasOwn(args, "content")) throw new Error("上下文 content 必须显式提供。");
} };
