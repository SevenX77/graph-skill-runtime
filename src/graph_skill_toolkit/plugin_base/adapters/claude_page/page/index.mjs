import { validateBrowserBridge } from "../../claude/connection/index.mjs";

/** The page half of the browser-page route: an authenticated same-origin link to
 * the plugin process.
 * @param {{snapshot:()=>any, fetch?:typeof globalThis.fetch, pageOrigin?:string}} options */
export function pageConnection({ snapshot, fetch: fetchImpl = globalThis.fetch?.bind(globalThis), pageOrigin = globalThis.location?.origin }) {
  let bridge = null, disposed = false;
  async function request(path, body) {
    if (disposed || !bridge) throw new Error("页面连接已关闭。");
    const response = await fetchImpl(bridge.url + path, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: "Bearer " + bridge.token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      cache: "no-store", credentials: "omit", redirect: "error",
    });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(value.error || "页面请求失败。");
    return value;
  }
  async function pollEvents(event) {
    let cursor = -1;
    while (!disposed) {
      try {
        const value = await request("/page/events?after=" + cursor);
        cursor = value.cursor;
        for (const item of value.events) if (!disposed) event(item);
      } catch { /* The next read retries; a transcript may not exist yet. */ }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
  return {
    request,
    async connect({ receive, fail }) {
      const payload = snapshot();
      if (payload?.error) return fail(new Error(payload.error));
      bridge = validateBrowserBridge(payload?.pageHost);
      if (!bridge) throw new Error("当前页面没有可用的插件连接。");
      if (pageOrigin !== undefined && new URL(bridge.url).origin !== pageOrigin) { bridge = null; throw new Error("页面与插件接口必须在同一来源。"); }
      receive(payload);
    },
    subscribeEvents(event) { void pollEvents(event); },
    /** @returns {Promise<import('../../../ports/host/index').HostEvidence>} */
    async inspect() {
      const value = await request("/page/capabilities");
      return { transport: "http-page", connected: !disposed && value.connected === true, identity: value.identity, capabilities: value.capabilities };
    },
    dispose() { disposed = true; bridge = null; },
  };
}

/** Theme, language and display mode belong to the page; the rest to the plugin process.
 * @returns {import('../../../ports/host/index').HostDriver} */
export function claudePageDriver(connection, { document: page = globalThis.document, window: view = globalThis.window, fullscreenWaitMs = 1500 } = {}) {
  const mode = () => page.fullscreenElement ? "fullscreen" : "inline";
  async function requestDisplayMode({ mode: wanted }) {
    if (wanted === "pip") return { status: "unsupported", message: "Claude 浏览器面板不能打开画中画窗口：requestWindow 报 no window。" };
    if (wanted === mode()) return { status: "completed", message: "页面已处于请求的显示模式。", data: { mode: wanted } };
    const change = wanted === "fullscreen" ? page.documentElement.requestFullscreen() : page.exitFullscreen();
    // The host may leave the request unanswered, so only the page's state decides.
    const failure = await Promise.race([Promise.resolve(change).then(() => null, error => String(error)), new Promise(resolve => setTimeout(() => resolve(null), fullscreenWaitMs))]);
    const actual = mode();
    if (actual === wanted) return { status: "completed", message: "页面已进入请求的显示模式。", data: { mode: actual } };
    return { status: "rejected", message: failure ?? `宿主在 ${fullscreenWaitMs} 毫秒内没有响应，页面未改变显示模式。`, data: { mode: actual }, evidence: { observed: { fullscreen: Boolean(page.fullscreenElement), waitedMs: fullscreenWaitMs } } };
  }
  return {
    async invoke(action, args = {}) {
      if (action === "views.requestDisplayMode") return requestDisplayMode(args);
      const result = await connection.request("/page/action", { action, args });
      if (action !== "host.getContext") return result;
      return { ...result, data: { ...result.data, theme: view.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light", locale: view.navigator?.language ?? null,
        displayMode: mode(), availableDisplayModes: ["inline", "fullscreen"] } };
    },
  };
}
