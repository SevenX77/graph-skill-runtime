// The Mod relays hook events through the page bridge; the facade owns subscribers.
export const capability = () => ({ state: "available", detail: "接收 Mod 转发的宿主事件：工具调用完成、对话轮次结束、会话结束、上下文已附上",
  constraints: { types: ["tool.completed", "turn.completed", "session.ended", "context.attached"] },
  limits: ["事件经 Mod 每秒一次的心跳转发，最多延迟约 1 秒；页面关闭期间产生的事件不会补发。"] });
