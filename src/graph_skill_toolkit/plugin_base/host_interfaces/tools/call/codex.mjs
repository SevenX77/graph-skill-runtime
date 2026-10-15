import { declared, responseResult, unsupported } from "../../../adapters/codex/driver/shared.mjs";
export const capability = host => declared(host.serverTools, "直接调用所属 MCP 服务的指定工具", { scope: "originating-server" });
export async function invoke(app, args, state) {
  if (args.tool.scope && args.tool.scope !== "originating-server") return unsupported("当前通道只允许所属 MCP 服务的工具调用。");
  if (args.tool.server && args.tool.server !== state.originatingServer) return unsupported("指定服务器与已确认的页面来源服务不一致。");
  return responseResult(await app.callServerTool({ name: args.tool.name, arguments: args.arguments }), "指定工具调用已返回。");
}
