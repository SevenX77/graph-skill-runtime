export const notSent = message => Object.assign(new Error(message), { outcome: "not-sent" });

export function nativeData(value) {
  if (value?.structuredContent) return value.structuredContent;
  if (value?.result !== undefined) return nativeData(value.result);
  if (value?.tabs || value?.tabId) return value;
  const blocks = Array.isArray(value?.content) ? value.content : [{ text: value?.text }];
  for (const block of blocks) {
    if (typeof block.text !== "string") continue;
    const text = block.text;
    // Parse an initial JSON object without executing text or consuming a
    // subsequent host visibility note as JSON.
    let start = text.indexOf("{"), depth = 0, quoted = false, escaped = false;
    if (start < 0) continue;
    for (let i = start; i < text.length; i++) {
      const c = text[i];
      if (quoted) { if (escaped) escaped = false; else if (c === "\\") escaped = true; else if (c === '"') quoted = false; }
      else if (c === '"') quoted = true;
      else if (c === "{") depth++;
      else if (c === "}" && --depth === 0) {
        try { return JSON.parse(text.slice(start, i + 1)); } catch { break; }
      }
    }
  }
  return value;
}

export async function callNative($, tools, name, args) {
  if (!tools.some(tool => tool.name === name)) throw notSent("当前会话未开放工具：" + name);
  if (Object.hasOwn(args, "tool") || Object.hasOwn(args, "tool_use_id")) throw notSent("此原生工具的平铺参数与宿主工具信封冲突；请使用明确的 MCP 服务标识。");
  const response = await $.tool.call({ ...args, tool: name });
  if (response?.deny || response?.denied) throw Object.assign(new Error("宿主拒绝工具请求。"), { outcome: "rejected" });
  if (response?.isError) return { status: "error", message: "原生工具返回错误。", data: response };
  return { status: "completed", message: "原生工具调用已返回。", data: response };
}

export async function callRequestedTool($, tools, reference, args) {
  if (reference.scope === "originating-server") return { status: "unsupported", message: "Claude 的通道按当前会话工具标识调用，请明确选择 session 范围。" };
  if (reference.server) {
    const name = "mcp__" + reference.server + "__" + reference.name;
    if (!tools.some(tool => tool.name === name && tool.mcp !== false)) return { status: "unsupported", message: "指定 MCP 工具未出现在当前会话清单中。", data: { server: reference.server, name: reference.name } };
    const response = await $.mcp.call(reference.server, reference.name, args);
    return { status: response?.isError ? "error" : "completed", message: "指定 MCP 工具调用已返回。", data: response };
  }
  if (!tools.some(tool => tool.name === reference.name)) return { status: "unsupported", message: "指定工具未出现在当前会话清单中。" };
  return callNative($, tools, reference.name, args);
}
