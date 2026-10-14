export const capability = () => ({ state: "available", detail: "读取当前会话实际开放的原生和 MCP 工具", scope: "session" });
export async function invoke(_$, { tools, args }) {
  if (args.scope === "originating-server") return { status: "unsupported", message: "此通道提供 session 工具清单，请选择对应范围。" };
  // Claude's ToolInfo is { name, description, mcp }; it does not include an input schema.
  // Missing optional-looking fields from an older host are marked unknown, not invented.
  if (!Array.isArray(tools) || tools.some(tool => !tool || typeof tool.name !== "string" || !tool.name ||
      (tool.description !== undefined && typeof tool.description !== "string") ||
      (tool.mcp !== undefined && typeof tool.mcp !== "boolean"))) {
    return { status: "error", message: "宿主未返回有效的当前会话工具清单。" };
  }
  const result = { status: "completed", message: "当前会话工具清单已返回。", data: { scope: "session", complete: true,
    tools: tools.map(tool => ({ name: tool.name, description: tool.description ?? null,
      kind: tool.mcp === undefined ? "unknown" : tool.mcp ? "mcp" : "native",
      reference: { name: tool.name, scope: "session" } })) } };
  // The Mod bridge otherwise drops data above 60,000 bytes while retaining a
  // completed status. Return a truthful bounded error instead of an empty list.
  if (new TextEncoder().encode(JSON.stringify(result)).length > 60000) {
    return { status: "error", message: "当前会话工具清单超过画布回执上限，无法完整返回。" };
  }
  return result;
}
