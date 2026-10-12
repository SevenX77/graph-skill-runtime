const capability = (available, detail) => ({ available: Boolean(available), detail });
const record = value => value !== null && typeof value === "object" && !Array.isArray(value);

export function mcpCapabilities(host) {
  if (!record(host)) throw new Error("MCP host capabilities are missing.");
  for (const name of ["message", "serverTools", "updateModelContext", "experimental"]) {
    if (host[name] !== undefined && !record(host[name])) throw new Error("Invalid MCP capability: " + name);
  }
  const files = host.experimental?.["openai/files"], draft = host.experimental?.["openai/message"]?.draft;
  if (files !== undefined && !record(files)) throw new Error("Invalid file capability.");
  if (draft !== undefined && !record(draft)) throw new Error("Invalid draft capability.");
  return {
    "open-root": capability(host.message, "请求当前 Agent 打开目录；回执不代表目录已经显示"),
    "open-file": capability(files || host.message, "打开当前 Skill 的 SKILL.md；宿主决定可用的文件视图"),
    "fill-prompt": capability(host.message && draft, draft ? "通过宿主草稿扩展追加文本，保留原草稿且不发送" : "宿主未声明可追加草稿的消息扩展"),
    "send-prompt": capability(host.message, "发送给当前宿主会话；回执仅代表请求被接受"),
    "update-context": capability(host.updateModelContext, "更新下一次模型请求读取的上下文，不启动会话"),
    "list-tools": capability(false, "当前接口仅能调用所属服务的已知工具，不能列出宿主全部工具"),
    "call-tool": capability(host.serverTools, "调用本画布服务的只读 inspect_graph"),
    "request-skill": capability(host.message, "请求 Agent 读取此 Skill 并概述；不直接执行业务图"),
  };
}

/** MCP connection only. Its peer can be any MCP Apps host. */
export function mcpConnection(app) {
  return {
    app,
    async connect({ receive, fail }) {
      app.ontoolresult = result => {
        if (result.isError) fail(new Error(result.content?.filter(item => item.type === "text").map(item => item.text).join("\n") || "Cannot display this Skill."));
        else receive(result.structuredContent);
      };
      await app.connect();
    },
    /** @returns {Promise<import('../../../ports/host/index').HostEvidence>} */
    async inspect() {
      let capabilities = null;
      try { capabilities = mcpCapabilities(app.getHostCapabilities()); } catch { /* Preserve identity facts; malformed capabilities cannot enable actions. */ }
      return { transport: "mcp-app", connected: app.state === "ready", identity: app.getHostVersion(), capabilities };
    },
    dispose() { return app.close(); },
  };
}
