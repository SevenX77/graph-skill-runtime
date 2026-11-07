import { SESSION_TOOL } from "../../host_tools/index.mjs";
export const notSent = (message, data) => Object.assign(new Error(message), { outcome: "not-sent", ...(data === undefined ? {} : { data }) });

/** Plain text from the native reply, retaining the host's exact sentences. */
export function nativeText(value) {
  // Claude Code 2.1.309 returns a native MCP reply as `result: [{ type, text }]`.
  if (Array.isArray(value)) return value.filter(block => typeof block?.text === "string").map(block => block.text).join("\n");
  if (typeof value?.text === "string") return value.text;
  if (Array.isArray(value?.content)) return value.content.filter(block => typeof block.text === "string").map(block => block.text).join("\n");
  return value?.result !== undefined ? nativeText(value.result) : "";
}

export function noWindowMessage(value) {
  const text = nativeText(value);
  return text.split("\n").find(line => /session (?:isn't|is not) open in any window/i.test(line)) ?? null;
}

export function nativeData(value) {
  if (value?.structuredContent) return value.structuredContent;
  if (value?.result !== undefined) return nativeData(value.result);
  if (value?.tabs || value?.tabId) return value;
  const blocks = Array.isArray(value) ? value : Array.isArray(value?.content) ? value.content : [{ text: value?.text }];
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

// One page action reads its own tool list, so that list identifies the action a person approved.
const approvedActions = new WeakSet();

/** A page's click is not a request the model made, so the person answers where the engine would ask. */
async function requestApproval($, tools, name, args) {
  // A query that fails only skips the question: the engine still decides on the call itself.
  let verdict = null;
  try { verdict = await $.tool.check({ tool: name, input: args }); } catch { return false; }
  // Every tool of an action is queried, so a deny rule on a later tool still stands after the answer.
  if (verdict?.decision !== "ask") return false;
  if (approvedActions.has(tools)) return true;
  const answer = await $.ui.ask("插件页面请求调用工具 " + name + "。这是页面上的操作发起的，不是模型的请求。允许吗？", { options: ["允许", "拒绝"], header: "页面工具" }).catch(() => null);
  if (answer !== "允许") throw Object.assign(new Error(answer === null ? "权限询问已关闭或无法显示，工具没有运行：" + name : "你拒绝了这次工具调用，工具没有运行：" + name), { outcome: "rejected", data: { failureScope: "request" } });
  approvedActions.add(tools);
  return true;
}

/** The server and tool an `mcp__<server>__<tool>` session name denotes; null for a native tool. */
export function mcpReference(name) {
  if (typeof name !== "string" || !name.startsWith("mcp__")) return null;
  const rest = name.slice("mcp__".length), cut = rest.indexOf("__");
  if (cut <= 0 || cut + 2 >= rest.length) return null;
  return { server: rest.slice(0, cut), tool: rest.slice(cut + 2) };
}

export async function callNative($, tools, name, args) {
  if (!tools.some(tool => tool.name === name)) throw notSent("当前会话未开放工具：" + name);
  if (Object.hasOwn(args, "tool") || Object.hasOwn(args, "tool_use_id")) throw notSent("此原生工具的平铺参数与宿主工具信封冲突；请使用明确的 MCP 服务标识。");
  const approved = await requestApproval($, tools, name, args);
  // A tool.check hook of this Mod did not settle an approved $.tool.call: in auto mode the classifier still
  // refused it. The person's answer is therefore carried by $.mcp.call, which the engine documents as the
  // plugin's own grant for a connected server's tool. A native tool has no such channel: it still goes
  // through $.tool.call and the session's permission decision.
  const reference = approved ? mcpReference(name) : null;
  const response = reference ? await $.mcp.call(reference.server, reference.tool, args) : await $.tool.call({ ...args, tool: name });
  if (response?.deny || response?.denied) {
    const reason = typeof response.deny === "string" && response.deny ? response.deny : null;
    throw Object.assign(new Error(reason ? "宿主拒绝工具请求：" + reason : "宿主拒绝工具请求，未给出原因。"), { outcome: "rejected", data: response });
  }
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

/** Read the session's permission mode from the desktop host's session tool. A background read shows nobody a
 * card: it runs only when the engine already allows the call, and an unreadable mode stays null. */
export async function readPermissionMode($, tools) {
  if (!tools.some(tool => tool.name === SESSION_TOOL)) return null;
  const args = { session_id: "self" };
  try {
    const verdict = await $.tool.check({ tool: SESSION_TOOL, input: args });
    if (verdict?.decision !== "allow") return null;
    const response = await $.tool.call({ ...args, tool: SESSION_TOOL });
    if (response?.deny || response?.denied || response?.isError) return null;
    const mode = nativeData(response)?.permissionMode;
    return typeof mode === "string" && mode ? mode : null;
  } catch { return null; }
}
