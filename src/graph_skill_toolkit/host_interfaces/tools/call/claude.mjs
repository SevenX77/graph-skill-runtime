import { callNative, notSent } from "../../../adapters/claude/mod/operations/tools/index.mjs";

export const capability = tools => ({
  state: tools.some(tool => typeof tool.name === "string") ? "available" : "unavailable",
  detail: "直接调用当前会话清单中的工具；调用经过宿主权限检查并返回原生结果",
  scope: "session",
});

export async function invoke($, { tools, args, guard }) {
  await guard();
  const reference = args.tool;
  // Mod tool.call treats these as host metadata, never as tool arguments.
  if (Object.hasOwn(args.arguments, "consent") || Object.hasOwn(args.arguments, "agentId")) {
    throw notSent("工具参数不能伪造宿主授权或 Agent 身份。");
  }
  if (reference.scope === "originating-server") return { status: "unsupported", message: "Claude 的通道按当前会话工具标识调用，请明确选择 session 范围。" };
  if (reference.server) {
    const name = "mcp__" + reference.server + "__" + reference.name;
    if (!tools.some(tool => tool.name === name && tool.mcp === true)) return {
      status: "unsupported", message: "指定 MCP 工具未出现在当前会话清单中；请使用清单中的完整名称。",
      data: { server: reference.server, name: reference.name },
    };
    return callNative($, tools, name, args.arguments);
  }
  if (!tools.some(tool => tool.name === reference.name)) return { status: "unsupported", message: "指定工具未出现在当前会话清单中。" };
  return callNative($, tools, reference.name, args.arguments);
}
