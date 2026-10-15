const LIMIT = "MCP App 宿主环境不含工作区目录；页面只能读到主题、语言、显示模式等宿主声明的字段。";
export const capability = (_host, context) => ({ state: context && typeof context === "object" ? "available" : "unknown",
  detail: "读取宿主交给 MCP App 的环境：主题、语言、显示模式等", limits: [LIMIT] });
export async function invoke(app) {
  const context = app.getHostContext?.();
  if (!context || typeof context !== "object") return { status: "error", message: "宿主没有提供 MCP App 环境。" };
  return { status: "completed", message: "已读取宿主环境。", data: { workspaceRoots: null, theme: context.theme ?? null, locale: context.locale ?? null,
    displayMode: context.displayMode ?? null, availableDisplayModes: context.availableDisplayModes ?? null, raw: context }, evidence: { receipt: context, limits: [LIMIT] } };
}
