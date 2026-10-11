// Claude attaches the HTTP preview origin, then navigates to this snapshot.
// The next graph tool call replaces its data and the host navigates again.
const ACTIONS = ["open-root", "open-file", "fill-prompt", "send-prompt", "update-context", "list-tools", "call-tool", "request-skill"];

export function validateBrowserBridge(value) {
  if (!value || typeof value.url !== "string" || typeof value.token !== "string") return null;
  const url = new URL(value.url);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port || url.username || url.password || url.search || url.hash ||
      !/^[A-Za-z0-9_-]{32,256}$/.test(value.token)) throw new Error("Claude 画布桥接地址无效。");
  return { url: value.url.replace(/\/$/, ""), token: value.token };
}

/** @returns {import('../../../ports/host/index').HostAdapter} */
export function claudeAdapter({ snapshot = () => JSON.parse(document.querySelector("#graph-skill-snapshot").textContent), clipboard = globalThis.navigator?.clipboard,
  fetch: fetchImpl = globalThis.fetch?.bind(globalThis), requestId = () => globalThis.crypto.randomUUID(), pageOrigin = globalThis.location?.origin } = {}) {
  let bridge = null, disposed = false;
  function requireConnection() {
    if (disposed) throw new Error("画布连接已关闭。");
    if (!bridge || !fetchImpl) throw new Error("当前 HTML 未连接 Claude 会话；请在会话中重新显示画布。");
  }
  async function request(path, body) {
    requireConnection();
    const response = await fetchImpl(bridge.url + path, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: "Bearer " + bridge.token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      cache: "no-store", credentials: "omit", redirect: "error",
    });
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      const error = new Error(value.message || value.error || "Claude 画布桥接请求失败。");
      error.requestRejected = [400,401,403,404,429].includes(response.status);
      throw error;
    }
    const value = await response.json();
    return value;
  }
  return {
    hostName: "Claude Code",
    rootActionLabel: "复制 Skill 文件夹路径",
    async connect({ receive, fail }) {
      const payload = snapshot();
      if (payload?.error) return fail(new Error(payload.error));
      bridge = validateBrowserBridge(payload?.hostBridge);
      if (bridge && pageOrigin !== undefined && new URL(bridge.url).origin !== pageOrigin) {
        bridge = null;
        return fail(new Error("请通过 Claude 的 HTTP 预览配置打开画布；当前页面与会话接口不在同一来源。"));
      }
      receive(payload);
    },
    async capabilities() {
      if (!bridge) return Object.fromEntries(ACTIONS.map(action => [action, { available: false, detail: "当前预览没有 Claude 会话连接" }]));
      const result = await request("/capabilities");
      return Object.fromEntries(ACTIONS.map(action => [action, result.connected && result.capabilities?.[action] ? result.capabilities[action] : {
        available: false, detail: "等待 Claude 会话中的画布适配器连接",
      }]));
    },
    async invoke(action, args = {}) {
      if (!ACTIONS.includes(action)) return { status: "unsupported", message: "未知的画布测试操作。" };
      requireConnection();
      const id = requestId();
      try { return await request("/action", { id, action, args }); }
      catch (error) {
        if (error.requestRejected) return {status:"rejected",message:error.message};
        // A lost HTTP response cannot tell us whether the Mod already acted.
        // Keep the identity so the UI queries this operation instead of resending.
        return {status:"pending",message:"提交结果未确认；请查询这次请求，避免重复执行。",requestId:id};
      }
    },
    async getResult(id) {
      if (typeof id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error("无效的画布请求编号。");
      return request("/result?id=" + encodeURIComponent(id));
    },
    async openRoot(root) {
      if (!clipboard) throw new Error("当前预览无法复制路径，请从顶部选择路径文本。");
      await clipboard.writeText(root);
      return "已复制 Skill 文件夹路径";
    },
    dispose() { disposed = true; bridge = null; },
  };
}
