import { record, string } from "../../validation/index.mjs";
export const definition = { id: "tools.call", label: "调用工具", sample: { tool: { name: "example_tool" }, arguments: {} }, fields: ["tool", "arguments"], validate(args) {
  const tool = record(args.tool);
  if (Object.keys(tool).some(key => !["name", "server", "scope"].includes(key)) || !string(tool.name) || (tool.server !== undefined && !string(tool.server)) || (tool.scope !== undefined && !["session", "originating-server"].includes(tool.scope))) throw new Error("无效的工具标识。");
  record(args.arguments);
} };
