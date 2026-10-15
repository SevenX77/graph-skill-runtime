import { string } from "../../validation/index.mjs";
export const definition = { id: "skills.invoke", label: "调用 Skill", sample: { skill: "example", input: "接口测试输入" }, fields: ["skill", "input"], validate(args) {
  if (!string(args.skill)) throw new Error("无效的 Skill 标识。");
} };
