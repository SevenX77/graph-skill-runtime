// The snapshot locates an authenticated connection; it cannot assert a host.
export function validateBrowserBridge(value) {
  if (!value || typeof value.url !== "string" || typeof value.token !== "string") return null;
  const url = new URL(value.url);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port || url.pathname !== "/" || url.username || url.password || url.search || url.hash ||
      !/^[A-Za-z0-9_-]{32,256}$/.test(value.token)) throw new Error("画布桥接地址无效。");
  return { url: url.origin, token: value.token };
}

/** @param {{snapshot:()=>unknown, fetch?:typeof globalThis.fetch, pageOrigin?:string}} options */
export function httpConnection({ snapshot, fetch: fetchImpl = globalThis.fetch?.bind(globalThis), pageOrigin = globalThis.location?.origin }) {
  let bridge = null, disposed = false;
  return {
    async connect({ receive, fail }) {
      const payload = snapshot();
      if (payload?.error) return fail(new Error(payload.error));
      bridge = validateBrowserBridge(payload?.hostBridge);
      if (!bridge) throw new Error("当前画布没有可用的会话连接。");
      if (pageOrigin !== undefined && new URL(bridge.url).origin !== pageOrigin) {
        bridge = null;
        throw new Error("请通过宿主 HTTP 预览打开画布；页面与会话接口必须在同一来源。");
      }
      receive(payload);
    },
    async request(path, body) {
      if (disposed) throw new Error("画布连接已关闭。");
      if (!bridge || !fetchImpl) throw new Error("当前 HTML 未连接宿主会话。");
      const response = await fetchImpl(bridge.url + path, {
        method: body === undefined ? "GET" : "POST",
        headers: { Authorization: "Bearer " + bridge.token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        cache: "no-store", credentials: "omit", redirect: "error",
      });
      if (!response.ok) {
        const value = await response.json().catch(() => ({}));
        const error = new Error(value.message || value.error || "画布桥接请求失败。");
        error.requestRejected = [400,401,403,404,429].includes(response.status);
        throw error;
      }
      return response.json();
    },
    /** @returns {Promise<import('../../../ports/host/index').HostEvidence>} */
    async inspect() {
      const value = await this.request("/capabilities");
      return { transport: "http-bridge", connected: !disposed && value.connected === true, identity: value.identity, capabilities: value.capabilities };
    },
    dispose() { disposed = true; bridge = null; },
  };
}
