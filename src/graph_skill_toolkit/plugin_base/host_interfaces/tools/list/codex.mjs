import { declared, responseResult, unsupported } from "../../../adapters/codex/driver/shared.mjs";
import { PAGE_TOOL_LIST_NAME } from "./index.mjs";
export const capability = host => declared(host.serverTools, "列出本页面所属 MCP 服务开放给页面的工具；不包含宿主其他工具", { scope: "originating-server" });
export async function invoke(app, args) {
  if (args.scope === "session") return unsupported("MCP App 只可列出所属服务的工具，不能枚举整个宿主会话。");
  const result = await app.callServerTool({ name: PAGE_TOOL_LIST_NAME, arguments: {} });
  if (result?.isError) return responseResult(result, "");
  const data = result?.structuredContent;
  if (!data || data.scope !== "originating-server" || !Array.isArray(data.tools)) return { status: "error", message: "所属 MCP 服务未返回有效工具清单。" };
  const seen = new Set();
  const tools = [];
  for (const tool of data.tools) {
    const name = tool?.name;
    if (typeof name !== "string" || !name || seen.has(name) ||
        (tool.description !== undefined && typeof tool.description !== "string") ||
        (tool.reference !== undefined && (tool.reference?.name !== name || tool.reference?.scope !== "originating-server" || tool.reference?.server !== undefined))) {
      return { status: "error", message: "所属 MCP 服务未返回有效工具清单。" };
    }
    seen.add(name);
    tools.push({ name, ...(tool.description === undefined ? {} : { description: tool.description }),
      reference: { name, scope: "originating-server" } });
  }
  const complete = data.complete === true;
  return { status: "completed", message: complete ? "已返回所属 MCP 服务的页面可调用工具。" : "已返回所属 MCP 服务的部分页面工具清单。",
    data: { scope: "originating-server", complete, tools } };
}
