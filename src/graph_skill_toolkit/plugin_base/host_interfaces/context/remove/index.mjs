import { string } from "../../validation/index.mjs";
export const definition = { id: "context.remove", label: "移除上下文", sample: { key: "example" }, fields: ["key"], validate(args) {
  if (!string(args.key) || ["__proto__", "constructor", "prototype"].includes(args.key)) throw new Error("无效的上下文 key。");
} };
