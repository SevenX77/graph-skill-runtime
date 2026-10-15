// The connection forwards MCP App notifications; the facade owns subscribers.
export const capability = () => ({ state: "available", detail: "接收 MCP App 通知：工具结果、宿主环境变化、页面即将关闭",
  constraints: { types: ["tool.completed", "host.contextChanged", "page.teardown"] },
  limits: ["MCP App 不通知对话轮次结束或会话结束；turn.completed 与 session.ended 在 Codex 上收不到。"] });
